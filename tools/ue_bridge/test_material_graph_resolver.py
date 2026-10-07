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

    def test_marks_missing_cooked_link_as_partial(self):
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "rawMaterialProperties": [
                        {
                            "name": "EmissiveColor",
                            "value": {
                                "kind": "FExpressionInput",
                                "expressionName": "MaterialExpressionDepthFade_2",
                                "resolvedExpression": None,
                            },
                        },
                    ],
                    "expressionGraph": [
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSampleParameter2D",
                            "objectPath": "/Game/Test/M.M:Texture",
                            "properties": [
                                {"name": "ParameterName", "value": "DIFF"},
                            ],
                        },
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
                    "colors": [],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }
        resolved = resolve_instance(root, "/Game/Test/MI.MI")
        self.assertEqual(resolved["graphStatus"], "partial")
        self.assertFalse(resolved["exactPinBindings"])
        self.assertEqual(
            resolved["unresolvedOutputInputs"]["EmissiveColor"],
            "MaterialExpressionDepthFade_2",
        )
        texture_rows = [
            row for row in resolved["parameterCandidates"]
            if row["kind"] == "texture"
        ]
        self.assertEqual(texture_rows[0]["parameter"], "DIFF")
        self.assertEqual(texture_rows[0]["boundValue"], "/Game/Test/T.T")

    def test_reconnects_expression_name_through_expression_graph(self):
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "rawMaterialProperties": [
                        {
                            "name": "EmissiveColor",
                            "value": {
                                "kind": "FExpressionInput",
                                "expressionName": "MaterialExpressionDepthFade_2",
                                "resolvedExpression": None,
                            },
                        },
                    ],
                    "expressionGraph": [
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionDepthFade",
                            "objectPath": "/Game/Test/M.M:MaterialExpressionDepthFade_2",
                            "properties": [
                                {
                                    "name": "Opacity",
                                    "value": {
                                        "kind": "FExpressionInput",
                                        "expressionName": "MaterialExpressionMultiply_0",
                                        "resolvedExpression": None,
                                    },
                                },
                            ],
                        },
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionMultiply",
                            "objectPath": "/Game/Test/M.M:MaterialExpressionMultiply_0",
                            "properties": [
                                {
                                    "name": "A",
                                    "value": {
                                        "kind": "FExpressionInput",
                                        "expressionName": "MaterialExpressionTextureSampleParameter2D_0",
                                        "resolvedExpression": None,
                                    },
                                },
                            ],
                        },
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSampleParameter2D",
                            "objectPath": "/Game/Test/M.M:MaterialExpressionTextureSampleParameter2D_0",
                            "properties": [
                                {"name": "ParameterName", "value": "DIFF"},
                            ],
                        },
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
                            "objectPath": "/Game/Test/T_Fire.T_Fire",
                        }
                    ],
                    "colors": [],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }

        resolved = resolve_instance(root, "/Game/Test/MI.MI")
        self.assertEqual(resolved["graphStatus"], "exact")
        self.assertTrue(resolved["exactPinBindings"])
        self.assertEqual(resolved["unresolvedOutputInputs"], {})
        emissive = resolved["pins"]["EmissiveColor"]
        texture_rows = [
            row for row in emissive
            if row["kind"] == "texture"
        ]
        self.assertEqual(texture_rows[0]["parameter"], "DIFF")
        self.assertEqual(
            texture_rows[0]["boundValue"],
            "/Game/Test/T_Fire.T_Fire",
        )

    def test_unique_direct_uv_texture_candidate(self):
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "semanticBaseMaterialPath": "/Game/Test/M.M",
                    "blendMode": "BLEND_Translucent",
                    "shadingModel": "MSM_Unlit",
                    "rawMaterialProperties": [
                        {
                            "name": "EmissiveColor",
                            "value": {
                                "kind": "FExpressionInput",
                                "expressionName": "MaterialExpressionMultiply_1",
                                "resolvedExpression": None,
                            },
                        },
                    ],
                    "expressionGraph": [
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSample",
                            "objectPath": "/Game/Test/M.M:Primary",
                            "properties": [
                                {
                                    "name": "Texture",
                                    "value": {
                                        "kind": "FPackageIndex",
                                        "path": "Texture2D'/Game/Test/Primary.Primary'",
                                    },
                                },
                            ],
                        },
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSample",
                            "objectPath": "/Game/Test/M.M:Panned",
                            "properties": [
                                {
                                    "name": "Coordinates",
                                    "value": {
                                        "kind": "FExpressionInput",
                                        "expressionName": "MaterialExpressionPanner_0",
                                    },
                                },
                                {
                                    "name": "Texture",
                                    "value": {
                                        "kind": "FPackageIndex",
                                        "path": "Texture2D'/Game/Test/Ripple.Ripple'",
                                    },
                                },
                            ],
                        },
                    ],
                    "textures": [
                        {"parameter": "ExpressionTexture_0_Texture", "objectPath": "/Game/Test/Primary.Primary"},
                        {"parameter": "ExpressionTexture_1_Texture", "objectPath": "/Game/Test/Ripple.Ripple"},
                    ],
                    "colors": [],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }
        resolved = resolve_instance(root, "/Game/Test/M.M")
        self.assertEqual(resolved["graphStatus"], "partial")
        self.assertEqual(
            resolved["partialPrimaryTextureCandidate"],
            "/Game/Test/Primary.Primary",
        )


    def test_partial_graph_unique_parent_texture_override(self):
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "rawMaterialProperties": [
                        {
                            "name": "EmissiveColor",
                            "value": {
                                "kind": "FExpressionInput",
                                "expressionName": "MaterialExpressionDepthFade_2",
                                "resolvedExpression": None,
                            },
                        },
                    ],
                    "expressionGraph": [
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSampleParameter2D",
                            "objectPath": "/Game/Test/M.M:Diff",
                            "properties": [
                                {"name": "ParameterName", "value": "DIFF"},
                            ],
                        },
                        {
                            "loaded": True,
                            "exportType": "MaterialExpressionTextureSampleParameter2D",
                            "objectPath": "/Game/Test/M.M:Emiss",
                            "properties": [
                                {"name": "ParameterName", "value": "EMISS"},
                            ],
                        },
                    ],
                    "textures": [
                        {"parameter": "DIFF", "objectPath": "/Engine/Black.Black"},
                        {"parameter": "EMISS", "objectPath": "/Game/Test/Black.Black"},
                    ],
                },
                {
                    "objectPath": "/Game/Test/MI.MI",
                    "exportType": "MaterialInstanceConstant",
                    "semanticBaseMaterialPath": "/Game/Test/M.M",
                    "blendMode": "BLEND_Additive",
                    "shadingModel": "MSM_Unlit",
                    "textures": [
                        {"parameter": "DIFF", "objectPath": "/Game/Test/Fire.Fire"},
                        {"parameter": "EMISS", "objectPath": "/Game/Test/Black.Black"},
                    ],
                    "colors": [],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }
        resolved = resolve_instance(root, "/Game/Test/MI.MI")
        self.assertEqual(resolved["graphStatus"], "partial")
        self.assertEqual(
            resolved["partialChangedTextureCandidate"],
            {
                "parameter": "diff",
                "baseValue": "/Engine/Black.Black",
                "boundValue": "/Game/Test/Fire.Fire",
            },
        )

    def test_partial_graph_multiple_parent_texture_overrides_are_ambiguous(self):
        root = {
            "materials": [
                {
                    "objectPath": "/Game/Test/M.M",
                    "exportType": "Material",
                    "rawMaterialProperties": [
                        {
                            "name": "EmissiveColor",
                            "value": {
                                "kind": "FExpressionInput",
                                "expressionName": "Missing",
                                "resolvedExpression": None,
                            },
                        },
                    ],
                    "expressionGraph": [],
                    "textures": [
                        {"parameter": "A", "objectPath": "/Game/Test/A0.A0"},
                        {"parameter": "B", "objectPath": "/Game/Test/B0.B0"},
                    ],
                },
                {
                    "objectPath": "/Game/Test/MI.MI",
                    "exportType": "MaterialInstanceConstant",
                    "semanticBaseMaterialPath": "/Game/Test/M.M",
                    "blendMode": "BLEND_Additive",
                    "shadingModel": "MSM_Unlit",
                    "textures": [
                        {"parameter": "A", "objectPath": "/Game/Test/A1.A1"},
                        {"parameter": "B", "objectPath": "/Game/Test/B1.B1"},
                    ],
                    "colors": [],
                    "scalars": [],
                    "switches": [],
                },
            ]
        }
        resolved = resolve_instance(root, "/Game/Test/MI.MI")
        self.assertIsNone(resolved["partialChangedTextureCandidate"])



if __name__ == "__main__":
    unittest.main()
