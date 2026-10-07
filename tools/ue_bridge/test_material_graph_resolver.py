import unittest

from material_graph_resolver import resolve_instance


def expr_input(expression):
    return {"kind": "FExpressionInput", "resolvedExpression": expression}


class MaterialGraphResolverTests(unittest.TestCase):
    def test_resolves_nested_emissive_texture_parameter(self):
        texture = {
            "exportType": "MaterialExpressionTextureSampleParameter2D",
            "objectPath": "/Game/Test/M.M:Texture",
            "properties": [
                {"name": "ParameterName", "value": "DIFF"},
            ],
        }
        multiply = {
            "exportType": "MaterialExpressionMultiply",
            "objectPath": "/Game/Test/M.M:Multiply",
            "properties": [
                {"name": "A", "value": expr_input(texture)},
                {
                    "name": "B",
                    "value": expr_input({
                        "exportType": "MaterialExpressionVectorParameter",
                        "objectPath": "/Game/Test/M.M:Color",
                        "properties": [
                            {"name": "ParameterName", "value": "Tint"},
                        ],
                    }),
                },
            ],
        }
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "rawMaterialProperties": [
                        {"name": "EmissiveColor", "value": expr_input(multiply)},
                    ],
                },
                {
                    "objectPath": "/Game/Test/MI.MI",
                    "exportType": "MaterialInstanceConstant",
                    "semanticBaseMaterialPath": "/Game/Test/M.M",
                    "blendMode": "BLEND_Additive",
                    "shadingModel": "MSM_Unlit",
                    "textures": [
                        {
                            "parameter": "DIFF",
                            "objectPath": "/Game/Test/T.T",
                        }
                    ],
                    "colors": [
                        {"name": "Tint", "value": [1, 0.5, 0.25, 1]},
                    ],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }

        resolved = resolve_instance(root, "/Game/Test/MI.MI")
        rows = resolved["pins"]["EmissiveColor"]
        texture_rows = [x for x in rows if x["kind"] == "texture"]
        vector_rows = [x for x in rows if x["kind"] == "vector"]
        self.assertEqual(texture_rows[0]["parameter"], "DIFF")
        self.assertEqual(texture_rows[0]["boundValue"], "/Game/Test/T.T")
        self.assertEqual(vector_rows[0]["parameter"], "Tint")
        self.assertEqual(vector_rows[0]["boundValue"], [1, 0.5, 0.25, 1])


if __name__ == "__main__":
    unittest.main()
