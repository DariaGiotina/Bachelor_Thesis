# Data sources and licences of the seed data

Covers `db/seed/seed_data.yaml` and everything generated from it (`db/postgres/seed.sql`, later `db/mongo/seed.js`).

## Products: Open Beauty Facts

- **What:** 14 of the 15 seed products (name, brand, barcode, quantity, ingredient list), fetched on 01.11.2026 from the public API of [Open Beauty Facts](https://world.openbeautyfacts.org) (`/api/v2/search`, categories facial creams, face masks, micellar waters, sunscreens). Products were kept only when they had a barcode, a brand and a short INCI list that could be read without guessing; two candidates were dropped because their lists were incomplete (a mineral sunscreen without its UV filter, a mask that lists only "CLAY").
- **Changes:** INCI names normalised to the CosIng spelling (translations in brackets removed, `WATER` and `AQUA / WATER` -> `AQUA`, `FRAGRANCE` -> `PARFUM`, `ALCOHOL DENAT` -> `ALCOHOL DENAT.`, the split `1` + `2-HEXANEDIOL` joined back); the category mapped to the app's value set; one quantity with an obvious typo (`30mk`) left empty. `BAMBOO CHARCOAL` is kept as printed on the label.
- **Licence:** the database is available under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) and its individual contents under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) ([data page](https://world.openbeautyfacts.org/data)). Obligations: attribute Open Beauty Facts wherever the data is shown (app product screen, thesis); a derived database that is published must be offered under the ODbL. Product photos have their own licence and are not used.
- **The last product** (`Demo Hydrating Serum (test entry)`, brand `Lumière demo`, no barcode) is not a real product: it is the author's test entry for the "product without barcode" case.

## Ingredients

- **INCI names and functions:** INCI names as in the products above; functions use the function names of [CosIng](https://single-market-economy.ec.europa.eu/sectors/cosmetics/cosmetic-ingredient-database_en), the European Commission's cosmetic ingredient database. In this seed they were assigned by the author and still have to be checked one by one against CosIng during the ingredient import (Task D3.5). CosIng is a Commission database; its reuse terms (Commission reuse policy, acknowledgement of the source) must be confirmed on the CosIng page before a bulk import.
- **Plain-language meaning:** the author's own wording.
- **Score (0-100) and flags:** curated by the author as an informational aid, not a safety assessment. Guideline: 85-95 for common, well-tolerated ingredients (water, glycerin, hyaluronates, mild emollients, thickeners, chelators); 70-84 for ingredients that are tolerated by most people but can bother very sensitive skin (some preservatives, propylene glycol, mineral oil, most UV filters); 40-69 for ingredients with a known reason for caution (exfoliating acids, retinol, drying alcohol, pore-clogging oils, cationic cleansers, avobenzone, methylparaben); below 40 for fragrance, the EU-labelled fragrance allergens and formaldehyde releasers. Flags name the reason (`fragrance`, `fragrance_allergen`, `drying_alcohol`, `exfoliating_acid`, `retinoid`, `comedogenic`, `formaldehyde_releaser`). The bands safe / caution / irritant (>= 70, 40-69, < 40) follow the product screen of the app design.
- `RETINOL` is in the list but in no product, on purpose (query "ingredients used by no product").

## Questionnaire

Questions, options and codes from `ml/features/field_mapping.md` and `ml/features/questionnaire_schema.yaml` (SCIN contributor app wording, SCIN v1.0.0, Google Research, [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE)), plus the red-flag question `lesion_change` written by the author (Task 4.2b). Options marked `is_red_flag`: bleeding, increasing in size, darkening, pain, and a recent change of the spot.

## Users and their data

All seven users, their analyses, routines, logs, consents and tokens are fictitious. E-mail addresses use the reserved domain `example.com`; passwords are throwaway values written in the seed file and stored in the databases only as Argon2id hashes; probabilities were written by hand and follow the decision rule of the exported model (threshold tau and the k-NN threshold of `ml/export/skin_concern_dinov2.json`); photo and heat-map keys point to no file. No real photo or personal data is part of the seed.

The seed is for local development, tests and demonstrations only: its passwords are public in this repository, so the user part of the seed must never be loaded into the production database (only the reference data: categories, zones, questions, ingredients, products).
