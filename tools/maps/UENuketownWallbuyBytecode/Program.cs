using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.Reflection;
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.Kismet.Bytecode;
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
var packageRows = new JArray();
var failures = new JArray();
var parsedFunctions = 0;
var parsedExpressions = 0;
var integerConstants = 0;

foreach (var assetPath in assetPaths)
{
    try
    {
        var asset = new UAsset(
            assetPath,
            EngineVersion.VER_UE5_1,
            mappings);

        var functionRows = new JArray();

        for (var exportIndex = 0; exportIndex < asset.Exports.Count; exportIndex++)
        {
            if (asset.Exports[exportIndex] is not FunctionExport function)
                continue;

            var flattened = new JArray();
            var constants = new JArray();
            var calls = new JArray();

            if (function.ScriptBytecode is { Length: > 0 })
            {
                parsedFunctions++;

                foreach (var root in function.ScriptBytecode)
                {
                    uint offset = 0;
                    root.Visit(
                        asset,
                        ref offset,
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

                            foreach (var member in InterestingMembers(expression))
                            {
                                row[member.Key] = member.Value;
                            }

                            var callName = CallName(expression);
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
                }
            }

            JToken rawJson;
            try
            {
                rawJson = function.ScriptBytecode is null
                    ? JValue.CreateNull()
                    : JToken.Parse(JsonConvert.SerializeObject(
                        function.ScriptBytecode,
                        Formatting.None,
                        new JsonSerializerSettings
                        {
                            NullValueHandling = NullValueHandling.Ignore,
                            ReferenceLoopHandling = ReferenceLoopHandling.Ignore
                        }));
            }
            catch (Exception e)
            {
                rawJson = new JObject
                {
                    ["serializationError"] =
                        e.GetType().Name + ": " + e.Message
                };
            }

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
                ["rawExpressionJson"] = rawJson
            });
        }

        packageRows.Add(new JObject
        {
            ["assetPath"] = assetPath,
            ["fileName"] = Path.GetFileName(assetPath),
            ["exportCount"] = asset.Exports.Count,
            ["functionCount"] = functionRows.Count,
            ["functions"] = functionRows
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
    parsedFunctions > 0 &&
    parsedExpressions > 0 &&
    integerConstants > 0;

var report = new JObject
{
    ["schemaVersion"] = 1,
    ["engineVersion"] = "VER_UE5_1",
    ["assetCount"] = assetPaths.Length,
    ["packageSuccessCount"] = packageRows.Count,
    ["failureCount"] = failures.Count,
    ["parsedFunctions"] = parsedFunctions,
    ["parsedExpressions"] = parsedExpressions,
    ["integerConstants"] = integerConstants,
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
    KismetExpression expression)
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
            ValueText(value));
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
            ValueText(value));
    }
}

static string CallName(KismetExpression expression)
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
                return ValueText(value);
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
