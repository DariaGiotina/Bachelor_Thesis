// =====================================================================================
// Probă pentru validatori (Task M4): documente invalide care trebuie respinse cu eroarea 121
// (DocumentValidationFailure), fiecare invalid printr-o singură valoare, pe o bază goală.
// Rulare, după setup.js, din folderul db/mongo:
//   mongosh --quiet mongodb://localhost:27017/skincare validator_samples.js
// Documentele sunt respinse, deci nu rămâne nimic în colecții. Pentru fiecare caz se afișează
// OK dacă a apărut eroarea așteptată și motivul dat de validator.
// =====================================================================================

const now = new Date();
let failures = 0;

function expectRejected(label, collection, doc) {
  try {
    db.getCollection(collection).insertOne(doc);
    print("FAIL  " + label + ": documentul a fost acceptat");
    db.getCollection(collection).deleteOne({ _id: doc._id });
    failures++;
  } catch (e) {
    if (e.code === 121) {
      const rule = JSON.stringify(e.errInfo && e.errInfo.details && e.errInfo.details.schemaRulesNotSatisfied || "").slice(0, 160);
      print("OK    " + label + " (121) " + rule);
    } else {
      print("FAIL  " + label + ": cod " + e.code + " " + e.message);
      failures++;
    }
  }
}

// 1. probabilitate în afara intervalului 0-1 (singura valoare greșită)
expectRejected("probability 1.2", "skin_analyses", {
  _id: UUID(), schema_version: 1, user_id: UUID(), created_at: now,
  model_version: "skin_concern_dinov2@0123456789abcdef", status: "answered", ood_score: 0.1,
  answers: [], zone_assessments: [], photo_ids: [],
  predictions: [
    { concern_code: "acne", probability: 1.2 }, { concern_code: "eczema_dermatitis", probability: 0 },
    { concern_code: "redness_rosacea", probability: 0 }, { concern_code: "normal_other", probability: 0 }],
});

// 2. cod de bare cu litere (singura valoare greșită)
expectRejected("barcode with letters", "products", {
  _id: UUID(), schema_version: 1, barcode: "12ab5678", name: "Test", brand: "Test",
  category: "cleanser", pack_size: null, source: "curated", ingredients: [],
  safety_score: null, flag_summary: { safe: 0, caution: 0, irritant: 0, flags: [] },
});

// 3. al doilea tip de fotografie: tip PROGRESS cu câmpul analysis_id (aparține tipului ANALYSIS)
expectRejected("PROGRESS photo with analysis_id", "photos", {
  _id: UUID(), schema_version: 1, user_id: UUID(), object_key: "photos/0d000000-0000-4000-8000-000000000001",
  content_type: "image/jpeg", captured_at: now, kind: "PROGRESS",
  log_id: UUID(), analysis_id: UUID(),
});

// 4. câmp necunoscut la nivelul de sus
expectRejected("unknown field", "face_zones", { _id: "forehead", schema_version: 1, zone_name: "Forehead", extra: 1 });

print(failures === 0 ? "VALIDATOR SAMPLES OK" : "VALIDATOR SAMPLES FAILED: " + failures);
if (failures) quit(1);
