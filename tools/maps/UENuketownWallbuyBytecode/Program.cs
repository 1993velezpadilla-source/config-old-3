using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.Reflection;
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.Kismet.Bytecode;
using UAssetAPI.PropertyTypes.Objects;
using UAssetAPI.UnrealTypes;
using UAssetAPI.Unversioned;

if (args.Length < 4)
{
    Console.Error.WriteLine(
        "usage: UENuketownWallbuyBytecode <mappings.usmap> <output.json> <asset.uasset> <asset.uasset> [...]");
    return 2;
}

var mappingsPath = args[0];
var outputPath = args[1];
var assetPaths = args.Skip(2).ToArray();

if (!File.Exists(mappingsPath))
    throw new FileNotFoundException("mappings missing", mappingsPath);

var mappings = new Usmap(mappingsPath);
var requestedEngineVersion = Environment.GetEnvironmentVariable("XZOGOT_ENGINE_VERSION");
var engineVersion = EngineVersion.VER_UE5_1;
if (!string.IsNullOrWhiteSpace(requestedEngineVersion) &&
    !Enum.TryParse<EngineVersion>(requestedEngineVersion, out engineVersion))
{
    throw new ArgumentException(
        $"Unknown XZOGOT_ENGINE_VERSION '{requestedEngineVersion}'");
}
Console.WriteLine($"XZOGOT_UASSET_ENGINE_VERSION {engineVersion}");
var packageRows = new JArray();
var failures = new JArray();
var parsedFunctions = 0;
var parsedExpressions = 0;
var integerConstants = 0;
var parsedDataTableRows = 0;
var parsedExportDefaults = 0;

foreach (var assetPath in assetPaths)
{
    try
    {
        var asset = new UAsset(
            assetPath,
            engineVersion,
            mappings);

        var functionRows = new JArray();
        var exportRows = new JArray();
        var dataTableRows = new JArray();

        for (var exportIndex = 0; exportIndex < asset.Exports.Count; exportIndex++)
        {
            if (asset.Exports[exportIndex] is not FunctionExport function)
                continue;

            var flattened = new JArray();
            var constants = new JArray();
            var calls = new JArray();

            var topLevelRows = new JArray();
            if (function.ScriptBytecode is { Length: > 0 })
            {
                parsedFunctions++;
                uint absoluteOffset = 0;

                foreach (var root in function.ScriptBytecode)
                {
                    var rootStartOffset = absoluteOffset;
                    root.Visit(
                        asset,
                        ref absoluteOffset,
                        (expression, inMemoryOffset) =>
                        {
                            parsedExpressions++;
                            var type = expression.GetType();
                            var row = new JObject
                            {
                                ["offset"] = inMemoryOffset,
                                ["token"] = expression.Token.ToString(),
                                ["type"] = type.Name
                            };

                            var valueProperty = type.GetProperty(
                                "Value",
                                BindingFlags.Public | BindingFlags.Instance);

                            if (valueProperty is not null)
                            {
                                object? value = null;
                                try { value = valueProperty.GetValue(expression); }
                                catch { }

                                if (value is not null)
                                {
                                    var valueText = ValueText(value);
                                    row["value"] = valueText;

                                    if (IsInteger(value))
                                    {
                                        constants.Add(new JObject
                                        {
                                            ["offset"] = inMemoryOffset,
                                            ["token"] = expression.Token.ToString(),
                                            ["type"] = type.Name,
                                            ["value"] = valueText
                                        });
                                        integerConstants++;
                                    }
                                }
                            }

                            foreach (var member in InterestingMembers(expression, asset))
                            {
                                row[member.Key] = member.Value;
                            }

                            var callName = CallName(expression, asset);
                            if (!string.IsNullOrWhiteSpace(callName))
                            {
                                calls.Add(new JObject
                                {
                                    ["offset"] = inMemoryOffset,
                                    ["token"] = expression.Token.ToString(),
                                    ["type"] = type.Name,
                                    ["call"] = callName
                                });
                            }

                            flattened.Add(row);
                        });
                    topLevelRows.Add(new JObject
                    {
                        ["startOffset"] = rootStartOffset,
                        ["endOffset"] = absoluteOffset,
                        ["expression"] = SafeObjectTree(root, asset, 0)
                    });
                }
            }

            var expressionTree = new JArray();
            if (function.ScriptBytecode is { Length: > 0 })
            {
                foreach (var rootExpression in function.ScriptBytecode)
                {
                    expressionTree.Add(
                        SafeObjectTree(rootExpression, asset, 0));
                }
            }

            JToken rawJson = expressionTree;

            functionRows.Add(new JObject
            {
                ["exportIndex"] = exportIndex,
                ["name"] = function.ObjectName.ToString(),
                ["functionFlags"] = function.FunctionFlags.ToString(),
                ["scriptBytecodeSize"] = function.ScriptBytecodeSize,
                ["scriptBytecodeParsed"] =
                    function.ScriptBytecode is { Length: > 0 },
                ["topLevelExpressionCount"] =
                    function.ScriptBytecode?.Length ?? 0,
                ["rawBytecodeBytes"] =
                    function.ScriptBytecodeRaw?.Length ?? 0,
                ["integerConstants"] = constants,
                ["calls"] = calls,
                ["expressions"] = flattened,
                ["rawExpressionJson"] = rawJson,
                ["topLevelExpressions"] = topLevelRows
            });
        }

        for (var exportIndex = 0; exportIndex < asset.Exports.Count; exportIndex++)
        {
            var export = asset.Exports[exportIndex];
            var exportRow = new JObject
            {
                ["exportIndex"] = exportIndex,
                ["name"] = export.ObjectName.ToString(),
                ["type"] = export.GetType().Name
            };

            if (export is NormalExport normal)
            {
                exportRow["data"] = SafeObjectTree(normal.Data, asset, 0);
                parsedExportDefaults += normal.Data?.Count ?? 0;
            }

            if (export is DataTableExport table &&
                table.Table?.Data is { Count: > 0 })
            {
                var rows = new JArray();
                foreach (var row in table.Table.Data)
                {
                    rows.Add(new JObject
                    {
                        ["name"] = row.Name.ToString(),
                        ["structType"] = row.StructType.ToString(),
                        ["data"] = SafeObjectTree(row.Value, asset, 0)
                    });
                    parsedDataTableRows++;
                }
                exportRow["dataTableRows"] = rows;
                dataTableRows.Add(new JObject
                {
                    ["exportIndex"] = exportIndex,
                    ["name"] = export.ObjectName.ToString(),
                    ["rows"] = rows
                });
            }

            exportRows.Add(exportRow);
        }

        var normalExportProperties = new JArray();
        var objectReferences = new JArray();
        for (var exportIndex = 0; exportIndex < asset.Exports.Count; exportIndex++)
        {
            if (asset.Exports[exportIndex] is not NormalExport normal)
                continue;

            JToken dataJson;
            try
            {
                dataJson = JToken.Parse(
                    asset.SerializeJsonObject(
                        normal.Data,
                        Newtonsoft.Json.Formatting.None));
            }
            catch (Exception e)
            {
                dataJson = new JObject
                {
                    ["serializationError"] = e.GetType().Name + ": " + e.Message
                };
            }

            normalExportProperties.Add(new JObject
            {
                ["exportIndex"] = exportIndex,
                ["objectName"] = normal.ObjectName.ToString(),
                ["properties"] = dataJson
            });

            if (normal.Data is not null)
            {
                foreach (var property in normal.Data)
                {
                    if (property is not ObjectPropertyData objectProperty)
                        continue;

                    objectReferences.Add(new JObject
                    {
                        ["exportIndex"] = exportIndex,
                        ["objectName"] = normal.ObjectName.ToString(),
                        ["propertyName"] = property.Name.ToString(),
                        ["rawIndex"] = objectProperty.Value.Index,
                        ["resolved"] = ResolveIndex(objectProperty.Value, asset)
                    });
                }
            }
        }

        var imports = new JArray();
        for (var importIndex = 0; importIndex < asset.Imports.Count; importIndex++)
        {
            var import = asset.Imports[importIndex];
            var rawIndex = -(importIndex + 1);
            imports.Add(new JObject
            {
                ["rawIndex"] = rawIndex,
                ["objectName"] = import.ObjectName.ToString(),
                ["className"] = import.ClassName.ToString(),
                ["classPackage"] = import.ClassPackage.ToString(),
                ["outerIndex"] = import.OuterIndex.Index,
                ["resolved"] = ResolveIndex(
                    FPackageIndex.FromRawIndex(rawIndex),
                    asset)
            });
        }

        packageRows.Add(new JObject
        {
            ["assetPath"] = assetPath,
            ["fileName"] = Path.GetFileName(assetPath),
            ["exportCount"] = asset.Exports.Count,
            ["importCount"] = asset.Imports.Count,
            ["imports"] = imports,
            ["normalExportProperties"] = normalExportProperties,
            ["objectReferences"] = objectReferences,
            ["functionCount"] = functionRows.Count,
            ["functions"] = functionRows,
            ["exports"] = exportRows,
            ["dataTables"] = dataTableRows
        });
    }
    catch (Exception e)
    {
        failures.Add(new JObject
        {
            ["assetPath"] = assetPath,
            ["error"] = e.GetType().FullName + ": " + e.Message,
            ["stack"] = e.StackTrace
        });
    }
}

var ready =
    failures.Count == 0 &&
    packageRows.Count == assetPaths.Length &&
    (
        (parsedFunctions > 0 && parsedExpressions > 0) ||
        parsedDataTableRows > 0 ||
        parsedExportDefaults > 0
    );

var report = new JObject
{
    ["schemaVersion"] = 1,
    ["engineVersion"] = engineVersion.ToString(),
    ["assetCount"] = assetPaths.Length,
    ["packageSuccessCount"] = packageRows.Count,
    ["failureCount"] = failures.Count,
    ["parsedFunctions"] = parsedFunctions,
    ["parsedExpressions"] = parsedExpressions,
    ["integerConstants"] = integerConstants,
    ["parsedDataTableRows"] = parsedDataTableRows,
    ["parsedExportDefaults"] = parsedExportDefaults,
    ["packages"] = packageRows,
    ["failures"] = failures,
    ["ready"] = ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    report.ToString(Formatting.Indented));

Console.WriteLine(
    "XZOGOT_NUKETOWN_WALLBUY_BYTECODE " +
    new JObject
    {
        ["assets"] = assetPaths.Length,
        ["packages"] = packageRows.Count,
        ["failures"] = failures.Count,
        ["functions"] = parsedFunctions,
        ["expressions"] = parsedExpressions,
        ["integerConstants"] = integerConstants,
        ["dataTableRows"] = parsedDataTableRows,
        ["exportDefaults"] = parsedExportDefaults,
        ["ready"] = ready
    }.ToString(Formatting.None));

if (!ready)
{
    Console.WriteLine("XZOGOT_NUKETOWN_WALLBUY_BYTECODE_FAILURE");
    return 5;
}

Console.WriteLine("XZOGOT_NUKETOWN_WALLBUY_BYTECODE_GREEN");
return 0;

static bool IsInteger(object value) =>
    value is byte or sbyte or short or ushort or int or uint or long or ulong;

static string ValueText(object value)
{
    if (value is null)
        return "";
    if (value is string s)
        return s;
    return value.ToString() ?? "";
}

static IEnumerable<KeyValuePair<string, JToken>> InterestingMembers(
    KismetExpression expression,
    UAsset asset)
{
    var names = new HashSet<string>(
        new[]
        {
            "VirtualFunctionName",
            "StackNode",
            "FunctionName",
            "Variable",
            "VariableExpression",
            "ObjectConst",
            "ClassPtr",
            "Property",
            "Context",
            "InterfaceClass",
            "Value"
        },
        StringComparer.OrdinalIgnoreCase);

    foreach (var field in expression.GetType().GetFields(
        BindingFlags.Public | BindingFlags.Instance))
    {
        if (!names.Contains(field.Name))
            continue;

        object? value = null;
        try { value = field.GetValue(expression); }
        catch { }

        if (value is null || value is KismetExpression)
            continue;

        yield return new KeyValuePair<string, JToken>(
            field.Name,
            ResolveValue(value, asset));
    }

    foreach (var prop in expression.GetType().GetProperties(
        BindingFlags.Public | BindingFlags.Instance))
    {
        if (!names.Contains(prop.Name) ||
            prop.GetIndexParameters().Length != 0 ||
            prop.Name is "Value")
            continue;

        object? value = null;
        try { value = prop.GetValue(expression); }
        catch { }

        if (value is null || value is KismetExpression)
            continue;

        yield return new KeyValuePair<string, JToken>(
            prop.Name,
            ResolveValue(value, asset));
    }
}

static JToken SafeObjectTree(object? value, UAsset asset, int depth)
{
    if (value is null)
        return JValue.CreateNull();

    if (depth > 10)
        return new JValue("<max-depth>");

    if (value is FPackageIndex packageIndex)
        return new JValue(ResolveIndex(packageIndex, asset));

    if (value is FName fname)
        return new JValue(fname.ToString());

    var type = value.GetType();

    if (value is string ||
        value is bool ||
        value is byte ||
        value is sbyte ||
        value is short ||
        value is ushort ||
        value is int ||
        value is uint ||
        value is long ||
        value is ulong ||
        value is float ||
        value is double ||
        value is decimal ||
        value is char)
        return JToken.FromObject(value);

    if (type.IsEnum)
        return new JValue(value.ToString());

    if (value is System.Collections.IEnumerable enumerable &&
        value is not string)
    {
        var array = new JArray();
        var count = 0;
        foreach (var item in enumerable)
        {
            if (count++ >= 512)
            {
                array.Add("<truncated>");
                break;
            }
            array.Add(SafeObjectTree(item, asset, depth + 1));
        }
        return array;
    }

    if (value is KismetExpression expression)
    {
        var row = new JObject
        {
            ["$type"] = type.Name,
            ["token"] = expression.Token.ToString()
        };

        foreach (var field in type.GetFields(
            BindingFlags.Public | BindingFlags.Instance))
        {
            if (field.Name is "Tag" or "RawValue")
                continue;
            object? fieldValue = null;
            try { fieldValue = field.GetValue(value); }
            catch { }
            if (fieldValue is null)
                continue;
            row[field.Name] = SafeObjectTree(
                fieldValue,
                asset,
                depth + 1);
        }

        var valueProperty = type.GetProperty(
            "Value",
            BindingFlags.Public | BindingFlags.Instance);
        if (valueProperty is not null &&
            valueProperty.GetIndexParameters().Length == 0)
        {
            try
            {
                var constantValue = valueProperty.GetValue(value);
                if (constantValue is not null)
                    row["Value"] = SafeObjectTree(
                        constantValue,
                        asset,
                        depth + 1);
            }
            catch { }
        }

        return row;
    }

    if (type.Namespace?.StartsWith("UAssetAPI", StringComparison.Ordinal) == true)
    {
        var row = new JObject
        {
            ["$type"] = type.Name
        };

        foreach (var field in type.GetFields(
            BindingFlags.Public | BindingFlags.Instance))
        {
            if (field.Name is "Asset" or "Owner" or "Tag" or "RawValue")
                continue;
            object? fieldValue = null;
            try { fieldValue = field.GetValue(value); }
            catch { }
            if (fieldValue is null)
                continue;
            row[field.Name] = SafeObjectTree(
                fieldValue,
                asset,
                depth + 1);
        }

        // PropertyData<T>.Value is an inherited public property rather than a
        // field. Dump it explicitly so DataTable rows and Blueprint defaults
        // retain their authoritative cooked values (weapon IDs, costs, enum
        // values, multipliers, etc.) instead of only property metadata.
        var mainValueProperty = type.GetProperty(
            "Value",
            BindingFlags.Public | BindingFlags.Instance);
        if (mainValueProperty is not null &&
            mainValueProperty.CanRead &&
            mainValueProperty.GetIndexParameters().Length == 0)
        {
            try
            {
                var mainValue = mainValueProperty.GetValue(value);
                if (mainValue is not null)
                    row["Value"] = SafeObjectTree(
                        mainValue,
                        asset,
                        depth + 1);
            }
            catch { }
        }

        return row;
    }

    return new JValue(ValueText(value));
}

static string ResolveIndex(FPackageIndex index, UAsset asset)
{
    if (index.IsNull())
        return "null";

    try
    {
        if (index.IsExport())
        {
            var export = index.ToExport(asset);
            return $"export:{index.Index}:{export.ObjectName}";
        }

        if (index.IsImport())
        {
            var parts = new List<string>();
            var current = index;
            var guard = 0;

            while (current.IsImport() && guard++ < 32)
            {
                var import = current.ToImport(asset);
                parts.Add(import.ObjectName.ToString());
                current = import.OuterIndex;
            }

            parts.Reverse();
            return $"import:{index.Index}:" + string.Join(".", parts);
        }
    }
    catch (Exception e)
    {
        return $"index:{index.Index}:resolve_error:{e.GetType().Name}";
    }

    return $"index:{index.Index}";
}

static JToken ResolveValue(object value, UAsset asset)
{
    if (value is FPackageIndex index)
        return ResolveIndex(index, asset);

    return ValueText(value);
}

static string CallName(KismetExpression expression, UAsset asset)
{
    var type = expression.GetType();
    foreach (var name in new[]
    {
        "VirtualFunctionName",
        "FunctionName",
        "StackNode"
    })
    {
        var field = type.GetField(
            name,
            BindingFlags.Public | BindingFlags.Instance);
        if (field is not null)
        {
            var value = field.GetValue(expression);
            if (value is not null)
                return ResolveValue(value, asset).ToString();
        }

        var prop = type.GetProperty(
            name,
            BindingFlags.Public | BindingFlags.Instance);
        if (prop is not null &&
            prop.GetIndexParameters().Length == 0)
        {
            var value = prop.GetValue(expression);
            if (value is not null)
                return ValueText(value);
        }
    }

    return "";
}
