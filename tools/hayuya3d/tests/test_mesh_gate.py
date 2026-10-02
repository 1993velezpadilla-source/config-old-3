from mesh_gate import _catastrophic_fragmentation_reason, _geometric_connectivity


def test_monja_shattered_surface_is_rejected():
    reason = _catastrophic_fragmentation_reason(1781, 0.012569)
    assert reason == "catastrophic_fragmentation:components=1781,largest=0.013"


def test_many_accessories_are_not_rejected_when_body_is_coherent():
    assert _catastrophic_fragmentation_reason(1400, 0.18) is None


def test_moderate_fragmentation_remains_telemetry_only():
    assert _catastrophic_fragmentation_reason(300, 0.02) is None


def test_uv_seam_vertex_duplicates_are_welded_for_connectivity():
    vertices=[
        (0.0,0.0,0.0),(1.0,0.0,0.0),(1.0,1.0,0.0),
        (0.0,0.0,0.0),(1.0,1.0,0.0),(0.0,1.0,0.0),
    ]
    faces=[(0,1,2),(3,4,5)]
    components,largest=_geometric_connectivity(vertices,faces,1.0)
    assert components==1
    assert largest==1.0


def test_true_separate_geometry_remains_separate_after_weld():
    vertices=[
        (0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0),
        (10.0,0.0,0.0),(11.0,0.0,0.0),(10.0,1.0,0.0),
    ]
    faces=[(0,1,2),(3,4,5)]
    components,largest=_geometric_connectivity(vertices,faces,11.0)
    assert components==2
    assert largest==0.5
