import results_registry as rr


def test_committed_tables_rebuild_from_results():
    assert rr.check_tables() == []


def test_registry_ids_unique_and_values_present():
    reg = rr.registry()
    assert reg["id"].is_unique
    assert (reg["value"].astype(str).str.len() > 0).all()
    assert set(reg["reported_in"]) >= {"8.1, Table 8.1", "8.5, Table 8.5", "8.6, Table 8.9"}
