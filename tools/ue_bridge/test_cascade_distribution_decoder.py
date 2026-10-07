import unittest

from cascade_distribution_decoder import (
    RDO_NONE,
    RDO_RANDOM,
    census_graphs,
    classify_table,
    decode_lookup_table,
    iter_lookup_tables,
)


class CascadeDistributionDecoderTests(unittest.TestCase):
    def test_float_constant(self):
        table = {
            "EntryCount": 1,
            "EntryStride": 1,
            "SubEntryStride": 1,
            "Op": RDO_NONE,
            "TimeScale": 0.0,
            "TimeBias": 0.0,
            "Values": [4.25],
        }
        self.assertEqual(classify_table(table), "constant")
        self.assertEqual(decode_lookup_table(table)["value"], 4.25)

    def test_float_uniform(self):
        table = {
            "EntryCount": 1,
            "EntryStride": 2,
            "SubEntryStride": 1,
            "Op": RDO_RANDOM,
            "TimeScale": 0.0,
            "TimeBias": 0.0,
            "Values": [2.0, 5.0],
        }
        decoded = decode_lookup_table(table)
        self.assertEqual(decoded["kind"], "uniform")
        self.assertEqual(decoded["min"], 2.0)
        self.assertEqual(decoded["max"], 5.0)

    def test_vector_constant_curve(self):
        table = {
            "EntryCount": 2,
            "EntryStride": 3,
            "SubEntryStride": 0,
            "Op": RDO_NONE,
            "TimeScale": 2.0,
            "TimeBias": 0.25,
            "Values": [1, 2, 3, 4, 5, 6],
        }
        decoded = decode_lookup_table(table)
        self.assertEqual(decoded["kind"], "constant_curve")
        self.assertEqual(decoded["dimension"], 3)
        self.assertEqual(decoded["keys"][0], {
            "time": 0.25,
            "interp": "linear",
            "value": [1.0, 2.0, 3.0],
        })
        self.assertEqual(decoded["keys"][1]["time"], 0.75)
        self.assertEqual(decoded["keys"][1]["value"], [4.0, 5.0, 6.0])

    def test_vector_uniform_curve(self):
        table = {
            "EntryCount": 2,
            "EntryStride": 6,
            "SubEntryStride": 3,
            "Op": RDO_RANDOM,
            "TimeScale": 4.0,
            "TimeBias": 0.0,
            "Values": [
                1, 2, 3, 10, 20, 30,
                4, 5, 6, 40, 50, 60,
            ],
        }
        decoded = decode_lookup_table(table)
        self.assertEqual(decoded["kind"], "uniform_curve")
        self.assertEqual(decoded["dimension"], 3)
        self.assertEqual(decoded["keys"][0]["min"], [1.0, 2.0, 3.0])
        self.assertEqual(decoded["keys"][0]["max"], [10.0, 20.0, 30.0])
        self.assertEqual(decoded["keys"][1]["time"], 0.25)
        self.assertEqual(decoded["keys"][1]["min"], [4.0, 5.0, 6.0])
        self.assertEqual(decoded["keys"][1]["max"], [40.0, 50.0, 60.0])

    def test_generic_value_and_value_aliases_do_not_duplicate_table(self):
        table = {
            "EntryCount": 1,
            "EntryStride": 2,
            "SubEntryStride": 1,
            "Op": RDO_RANDOM,
            "TimeScale": 0.0,
            "TimeBias": 0.0,
            "Values": [2.0, 5.0],
        }
        wrapped = {
            "kind": "CUE4Parse.Test.Property",
            "members": {
                "GenericValue": {"Table": table},
                "Value": {"Table": table},
            },
        }
        rows = list(iter_lookup_tables(wrapped))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["Values"], [2.0, 5.0])

    def test_census_reports_node_and_property_context(self):
        table = {
            "EntryCount": 1,
            "EntryStride": 2,
            "SubEntryStride": 1,
            "Op": RDO_RANDOM,
            "TimeScale": 0.0,
            "TimeBias": 0.0,
            "Values": [1.0, 3.0],
        }
        graphs = {
            "systems": [
                {
                    "objectPath": "/Game/Test/P.P",
                    "nodes": [
                        {
                            "objectPath": "/Game/Test/P.P:ParticleModuleLifetime_0",
                            "exportType": "ParticleModuleLifetime",
                            "properties": [
                                {
                                    "name": "Lifetime",
                                    "value": {
                                        "kind": "CUE4Parse.Test.Property",
                                        "members": {
                                            "GenericValue": {"Table": table},
                                            "Value": {"Table": table},
                                        },
                                    },
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        report = census_graphs(graphs)
        self.assertEqual(report["total"], 1)
        self.assertEqual(
            report["nodeTypes"]["ParticleModuleLifetime"],
            1,
        )
        self.assertEqual(report["properties"]["Lifetime"], 1)


    def test_census_accepts_dictionary_properties_like_nacht_authority(self):
        table = {
            "EntryCount": 1,
            "EntryStride": 2,
            "SubEntryStride": 1,
            "Op": RDO_RANDOM,
            "TimeScale": 0.0,
            "TimeBias": 0.0,
            "Values": [2.7, 2.8],
        }
        graphs = {
            "systems": [
                {
                    "objectPath": "/Game/Test/P.P",
                    "nodes": [
                        {
                            "objectPath": "/Game/Test/P.P:ParticleModuleLifetime_0",
                            "exportType": "ParticleModuleLifetime",
                            "properties": {
                                "LODValidity": 1.0,
                                "Lifetime": {
                                    "expanded": True,
                                    "kind": "FScriptStruct",
                                    "structType": "CUE4Parse.UE4.Assets.Objects.FStructFallback",
                                    "value": {
                                        "kind": "FStructFallback",
                                        "properties": [
                                            {
                                                "name": "Distribution",
                                                "value": {
                                                    "kind": "FPackageIndex",
                                                    "index": 0,
                                                    "path": None,
                                                },
                                            },
                                            {"name": "MinValue", "value": 2.7},
                                            {"name": "MaxValue", "value": 2.8},
                                            {
                                                "name": "Table",
                                                "value": {
                                                    "kind": "FScriptStruct",
                                                    "value": {
                                                        "kind": "FStructFallback",
                                                        "properties": [
                                                            {"name": "EntryCount", "value": 1},
                                                            {"name": "EntryStride", "value": 2},
                                                            {"name": "SubEntryStride", "value": 1},
                                                            {"name": "Op", "value": RDO_RANDOM},
                                                            {"name": "TimeScale", "value": 0.0},
                                                            {"name": "TimeBias", "value": 0.0},
                                                            {"name": "Values", "value": [2.7, 2.8]},
                                                        ],
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                },
                            },
                        },
                    ],
                },
            ],
        }
        report = census_graphs(graphs)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["counts"]["uniform"], 1)
        self.assertEqual(report["properties"]["Lifetime"], 1)
        self.assertEqual(
            report["rows"][0]["systemPath"],
            "/Game/Test/P.P",
        )



if __name__ == "__main__":
    unittest.main()
