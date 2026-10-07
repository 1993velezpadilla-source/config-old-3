import unittest

from cascade_distribution_decoder import (
    RDO_NONE,
    RDO_RANDOM,
    classify_table,
    decode_lookup_table,
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


if __name__ == "__main__":
    unittest.main()
