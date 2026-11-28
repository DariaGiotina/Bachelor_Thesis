// =====================================================================================
// Structura bazei MongoDB (Task M4): colecții cu validator, indexuri și vederi.
// Se poate rula de oricâte ori (idempotent). Din folderul db/mongo:
//   mongosh --quiet mongodb://localhost:27017/skincare setup.js
//
// Parametri opționali, setați înainte de load("setup.js"):
//   var targetDb = "nume";   baza de date țintă (implicit "skincare")
//   var withTtl  = false;    nu crea indexurile TTL (implicit true)
// Indexurile TTL șterg singure documentele expirate. Datele de test (seed.js) au tokenuri
// cu data expirării în trecut față de data reală, deci pe baza de demonstrație ele se
// omit; pe baza reală (și pe Atlas) trebuie create.
//
// Validatorii sunt în schema/<colecție>.json, o singură sursă folosită de mongosh și, mai
// târziu, de backend. Regulile pe care un validator nu le poate exprima sunt listate în
// schema/not_in_validators.md, cu locul unde se aplică.
// =====================================================================================

const fs = require("fs");
const d = db.getSiblingDB(typeof targetDb === "undefined" ? "skincare" : targetDb);
const ttl = typeof withTtl === "undefined" ? true : withTtl;

// -------------------------------------------------------------------------------------
// 1. Colecțiile, fiecare cu validatorul ei (strict + error: un document invalid este respins)
// -------------------------------------------------------------------------------------
const COLLECTIONS = [
  "users", "consents", "one_time_tokens", "refresh_tokens",
  "skin_analyses", "photos", "questions", "skin_concerns", "face_zones",
  "products", "ingredients", "routines", "daily_logs",
];

for (const name of COLLECTIONS) {
  const schema = JSON.parse(fs.readFileSync("schema/" + name + ".json", "utf8"));
  const validator = { $jsonSchema: schema };
  if (d.getCollectionInfos({ name }).length === 0) {
    d.createCollection(name, { validator, validationLevel: "strict", validationAction: "error" });
    print("collection created: " + name);
  } else {
    d.runCommand({ collMod: name, validator, validationLevel: "strict", validationAction: "error" });
    print("validator updated:  " + name);
  }
}

// -------------------------------------------------------------------------------------
// 2. Indexurile, fiecare cu interogarea pe care o servește (nume explicit => rulare repetabilă)
// -------------------------------------------------------------------------------------
// [colecție, cheie, opțiuni]
const INDEXES = [
  // autentificare: căutare după e-mail (salvat cu litere mici), unic
  ["users", { email: 1 }, { name: "uq_users_email", unique: true }],

  // verificare e-mail / resetare parolă: căutare după hash; lista unui utilizator
  ["one_time_tokens", { token_hash: 1 }, { name: "uq_one_time_tokens_hash", unique: true }],
  ["one_time_tokens", { user_id: 1 }, { name: "ix_one_time_tokens_user" }],

  // reînnoire token: după hash; revocarea familiei; ștergerea contului după user_id
  ["refresh_tokens", { token_hash: 1 }, { name: "uq_refresh_tokens_hash", unique: true }],
  ["refresh_tokens", { family_id: 1 }, { name: "ix_refresh_tokens_family" }],
  ["refresh_tokens", { user_id: 1 }, { name: "ix_refresh_tokens_user" }],

  // verificarea consimțământului înainte de încărcarea unei fotografii
  ["consents", { user_id: 1, consent_type: 1 }, { name: "ix_consents_user_type" }],

  // istoric paginat: analizele unui utilizator, cele mai noi întâi
  ["skin_analyses", { user_id: 1, created_at: -1 }, { name: "ix_skin_analyses_user_created" }],

  // fotografii: cheia obiectului unică; după utilizator și tip; o fotografie de progres pe zi;
  // cheia hărții de căldură unică atunci când există
  ["photos", { object_key: 1 }, { name: "uq_photos_object_key", unique: true }],
  ["photos", { user_id: 1, kind: 1 }, { name: "ix_photos_user_kind" }],
  ["photos", { log_id: 1 }, { name: "uq_photos_log", unique: true, partialFilterExpression: { log_id: { $type: "binData" } } }],
  ["photos", { heatmap_key: 1 }, { name: "uq_photos_heatmap", unique: true, partialFilterExpression: { heatmap_key: { $type: "string" } } }],

  // chestionar și date de referință: câmpul de cod și numele sunt unice
  ["questions", { field_key: 1 }, { name: "uq_questions_field_key", unique: true }],
  ["skin_concerns", { name: 1 }, { name: "uq_skin_concerns_name", unique: true }],
  ["face_zones", { zone_name: 1 }, { name: "uq_face_zones_name", unique: true }],

  // scanare cod de bare: unic doar când codul există (mai multe produse pot să nu aibă cod)
  ["products", { barcode: 1 }, { name: "uq_products_barcode", unique: true, partialFilterExpression: { barcode: { $type: "string" } } }],
  // căutare text în nume și marcă
  ["products", { name: "text", brand: "text" }, { name: "ix_products_text" }],

  // ingredient după numele INCI, fără a ține cont de majuscule (collation strength 2)
  ["ingredients", { inci_name: 1 }, { name: "uq_ingredients_inci", unique: true, collation: { locale: "en", strength: 2 } }],

  // rutina zilei: ultima rutină a unui utilizator pentru o perioadă (created_at descrescător)
  ["routines", { user_id: 1, period: 1, created_at: -1 }, { name: "ix_routines_user_period_created" }],

  // jurnal: o singură înregistrare pe zi și pe utilizator; același index servește calendarul lunii
  ["daily_logs", { user_id: 1, log_date: 1 }, { name: "uq_daily_logs_user_date", unique: true }],
];

if (ttl) {
  // tokenurile expirate se șterg singure (verificarea rulează cam o dată pe minut)
  INDEXES.push(["one_time_tokens", { expires_at: 1 }, { name: "ttl_one_time_tokens_expires", expireAfterSeconds: 0 }]);
  INDEXES.push(["refresh_tokens", { expires_at: 1 }, { name: "ttl_refresh_tokens_expires", expireAfterSeconds: 0 }]);
} else {
  print("TTL indexes skipped (withTtl = false)");
}

for (const [coll, key, options] of INDEXES) {
  d.getCollection(coll).createIndex(key, options);
}
print("indexes ensured: " + INDEXES.length);

// -------------------------------------------------------------------------------------
// 3. Vederile atributelor derivate (oglinda vederilor Oracle din queries.sql, secțiunea 1);
//    o vedere MongoDB este un pipeline de agregare salvat, calculat la fiecare citire
// -------------------------------------------------------------------------------------
const VIEWS = {
  // 1.1 rezultatul unei analize: încrederea generală = cea mai mare probabilitate, categoria
  //     principală doar pentru status answered (egalitățile se departajează după cod)
  v_analysis_result: ["skin_analyses", [
    { $match: { "predictions.0": { $exists: true } } },
    { $set: { sorted: { $sortArray: { input: "$predictions", sortBy: { probability: -1, concern_code: 1 } } } } },
    { $project: {
        _id: 0, analysis_id: "$_id", user_id: 1, created_at: 1, status: 1,
        overall_confidence: { $max: "$predictions.probability" },
        top_concern: { $cond: [{ $eq: ["$status", "answered"] }, { $first: "$sorted.concern_code" }, null] },
    } },
  ]],

  // 1.2 locul fiecărei categorii într-o analiză (1 = cea mai mare probabilitate)
  v_prediction_rank: ["skin_analyses", [
    { $project: { _id: 0, analysis_id: "$_id", preds: { $sortArray: { input: "$predictions", sortBy: { probability: -1, concern_code: 1 } } } } },
    { $unwind: { path: "$preds", includeArrayIndex: "idx" } },
    { $project: { analysis_id: 1, concern_code: "$preds.concern_code", probability: "$preds.probability", rank: { $add: ["$idx", 1] } } },
  ]],

  // 1.3 profilul utilizatorului cu vârsta (ani împliniți) și grupa de vârstă la data curentă
  v_user_profile: ["users", [
    { $set: { birthdays: { $dateDiff: { startDate: "$date_of_birth", endDate: "$$NOW", unit: "year" } } } },
    { $set: { age: { $cond: [
        { $gt: [{ $dateAdd: { startDate: "$date_of_birth", unit: "year", amount: "$birthdays" } }, "$$NOW"] },
        { $subtract: ["$birthdays", 1] }, "$birthdays"] } } },
    { $project: {
        _id: 0, user_id: "$_id", first_name: 1, skin_profile: 1, language: 1, age: 1,
        age_range: { $switch: { branches: [
          { case: { $lt: ["$age", 20] }, then: "18-19" },
          { case: { $lt: ["$age", 30] }, then: "20-29" },
          { case: { $lt: ["$age", 40] }, then: "30-39" },
          { case: { $lt: ["$age", 50] }, then: "40-49" },
          { case: { $lt: ["$age", 60] }, then: "50-59" },
        ], default: "60+" } },
    } },
  ]],

  // 1.4 scorul de siguranță al produsului: media scorurilor ingredientelor ponderată cu
  //     1/poziție, rotunjită; numărul de ingrediente pe benzi și marcajele distincte.
  //     Scorurile se iau din ingredients, deci vederea rămâne corectă și când câmpul
  //     safety_score păstrat în products nu a fost încă recalculat
  v_product_safety: ["products", [
    { $lookup: { from: "ingredients", localField: "ingredients.ingredient_id", foreignField: "_id", as: "ing" } },
    { $set: { items: { $map: { input: "$ingredients", as: "pi", in: {
        position: "$$pi.position",
        ing: { $first: { $filter: { input: "$ing", as: "i", cond: { $eq: ["$$i._id", "$$pi.ingredient_id"] } } } },
    } } } } },
    { $set: { items: { $map: { input: "$items", as: "x", in: { w: { $divide: [1, "$$x.position"] }, score: "$$x.ing.score", flags: "$$x.ing.flags" } } } } },
    { $project: {
        _id: 0, product_id: "$_id", name: 1, brand: 1, category: 1,
        safety_score: { $cond: [{ $eq: [{ $size: "$items" }, 0] }, null,
          { $round: [{ $divide: [
            { $sum: { $map: { input: "$items", as: "x", in: { $multiply: ["$$x.score", "$$x.w"] } } } },
            { $sum: "$items.w" }] }, 0] }] },
        ingredients: { $size: "$items" },
        safe_count: { $size: { $filter: { input: "$items", as: "x", cond: { $gte: ["$$x.score", 70] } } } },
        caution_count: { $size: { $filter: { input: "$items", as: "x", cond: { $and: [{ $gte: ["$$x.score", 40] }, { $lt: ["$$x.score", 70] }] } } } },
        irritant_count: { $size: { $filter: { input: "$items", as: "x", cond: { $lt: ["$$x.score", 40] } } } },
        flags: { $sortArray: { input: { $setUnion: [{ $reduce: { input: "$items.flags", initialValue: [], in: { $concatArrays: ["$$value", "$$this"] } } }, []] }, sortBy: 1 } },
    } },
  ]],
};

for (const [view, [source, pipeline]] of Object.entries(VIEWS)) {
  d.getCollection(view).drop();            // vederea se recreează la fiecare rulare
  d.createView(view, source, pipeline);
}
print("views (re)created: " + Object.keys(VIEWS).join(", "));
print("setup finished on database " + d.getName());
