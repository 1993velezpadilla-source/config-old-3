using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

if (args.Length < 4)
{
    Console.Error.WriteLine(
        "usage: UENuketownGameplayTruth <unpacked-root> <mappings.usmap> <output-json> <package> [package...]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var outputPath = args[2];
var targets = args.Skip(3).ToArray();

if (!Directory.Exists(root))
    throw new DirectoryNotFoundException(root);
if (!File.Exists(mappingsPath))
    throw new FileNotFoundException("mappings missing", mappingsPath);

var sourceGameName =
    Environment.GetEnvironmentVariable("XZOGOT_SOURCE_GAME")?.Trim().ToLowerInvariant()
    ?? "ue5.1";
EGame sourceGame =
    sourceGameName switch
    {
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        "ue5.7" or "ue5_7" or "ue57" => EGame.GAME_UE5_7,
        _ => throw new ArgumentException(
            "unsupported XZOGOT_SOURCE_GAME: " + sourceGameName)
    };

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    true,
    new VersionContainer(sourceGame))
{
    MappingsContainer = new FileUsmapTypeMappingsProvider(mappingsPath)
};

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var serializer = Newtonsoft.Json.JsonSerializer.Create(
    new JsonSerializerSettings
    {
        NullValueHandling = NullValueHandling.Ignore,
        ReferenceLoopHandling = ReferenceLoopHandling.Ignore,
        Formatting = Formatting.None
    });

var wantedLevelClasses = new HashSet<string>(
    new[]
    {
        "wallbuy_C",
        "wallbuy_2_C",
        "wallbuy_3_C",
        "NewBlueprint1_2_C",
        "BuyWheelBox_2_C",
        "Pavlov_Spawn",
        "Pavlov_Ladder",
        "AmbientSound",
        "AudioComponent",
        "SkyAtmosphere",
        "SkyAtmosphereComponent",
        "SkyLight",
        "SkyLightComponent",
        "DirectionalLight",
        "DirectionalLightComponent",
        "ExponentialHeightFog",
        "ExponentialHeightFogComponent",
        "VolumetricCloud",
        "VolumetricCloudComponent",
        "speed_C",
        "tpout1_C",
        "viptp_C",
        "cash_text_C",
        "disgod_C",
        "OldFashionedGod_C",
        "Enter_your_key_C",
        "GamemodeDetector_C",
        "JoinSounds_C",
        "JoinSounds_2_C",
        "JoinSounds_3_C",
        "NewBlueprint_C",
        "NewBlueprint_11_C",
        "NewBlueprint_19_C",
    },
    StringComparer.Ordinal);

var packageRows = new JArray();
var packageFailures = new JArray();
var totalExports = 0;
var dumpedExports = 0;
var dumpedProperties = 0;
var dumpedFunctions = 0;

foreach (var logicalPath in targets)
{
    var resolved = ResolveProviderPackagePath(provider, logicalPath);
    if (resolved is null)
    {
        packageFailures.Add(new JObject
        {
            ["packagePath"] = logicalPath,
            ["error"] = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        var exports = new JArray();
        var isLevel = logicalPath.EndsWith(
            "nuketownz.umap",
            StringComparison.OrdinalIgnoreCase);

        totalExports += package.ExportMapLength;

        for (var exportIndex = 0; exportIndex < package.ExportMapLength; ++exportIndex)
        {
            var export = package.GetExport(exportIndex);
            if (export is null)
                continue;

            if (isLevel && !wantedLevelClasses.Contains(export.ExportType))
                continue;

            var properties = new JArray();
            foreach (var property in export.Properties)
            {
                properties.Add(new JObject
                {
                    ["name"] = property.Name.Text,
                    ["arrayIndex"] = property.ArrayIndex,
                    ["tagType"] = property.Tag?.GetType().FullName,
                    ["value"] = SafeToken(property.Tag, serializer)
                });
                dumpedProperties++;
            }

            JToken? scriptBytecode = null;
            var scriptStatementCount = 0;
            if (export is UFunction function &&
                function.ScriptBytecode is { Length: > 0 })
            {
                scriptStatementCount = function.ScriptBytecode.Length;
                scriptBytecode = SafeToken(function.ScriptBytecode, serializer);
                dumpedFunctions++;
            }

            JToken? classDefaultProperties = null;
            JToken? classFunctions = null;
            string? pseudo = null;
            if (export is UClass klass)
            {
                var defaults = klass.ClassDefaultObject.Load();
                if (defaults is not null)
                {
                    var defaultRows = new JArray();
                    foreach (var property in defaults.Properties)
                    {
                        defaultRows.Add(new JObject
                        {
                            ["name"] = property.Name.Text,
                            ["arrayIndex"] = property.ArrayIndex,
                            ["tagType"] = property.Tag?.GetType().FullName,
                            ["value"] = SafeToken(property.Tag, serializer)
                        });
                        dumpedProperties++;
                    }
                    classDefaultProperties = defaultRows;
                }

                var functionRows = new JArray();
                foreach (var (functionName, functionRef) in klass.FuncMap)
                {
                    if (!functionRef.TryLoad(out var functionExport) ||
                        functionExport is not UFunction loadedFunction)
                        continue;

                    var statementCount =
                        loadedFunction.ScriptBytecode?.Length ?? 0;
                    var row = new JObject
                    {
                        ["name"] = functionName.Text,
                        ["exportName"] = loadedFunction.Name,
                        ["functionFlags"] = loadedFunction.FunctionFlags.ToString(),
                        ["scriptStatementCount"] = statementCount,
                        ["scriptBytecode"] =
                            statementCount > 0
                                ? SafeToken(
                                    loadedFunction.ScriptBytecode,
                                    serializer)
                                : JValue.CreateNull()
                    };
                    functionRows.Add(row);
                    if (statementCount > 0)
                        dumpedFunctions++;
                }
                classFunctions = functionRows;

                try
                {
                    pseudo = klass.DecompileBlueprintToPseudo();
                }
                catch (Exception e)
                {
                    pseudo =
                        "DECOMPILE_ERROR: " +
                        e.GetType().Name + ": " + e.Message;
                }
            }

            exports.Add(new JObject
            {
                ["exportIndex"] = exportIndex,
                ["name"] = export.Name,
                ["exportType"] = export.ExportType,
                ["propertyCount"] = export.Properties.Count,
                ["properties"] = properties,
                ["scriptStatementCount"] = scriptStatementCount,
                ["scriptBytecode"] = scriptBytecode,
                ["classDefaultProperties"] = classDefaultProperties,
                ["classFunctions"] = classFunctions,
                ["decompiledPseudo"] = pseudo
            });
            dumpedExports++;
        }

        var imports = new JArray();
        if (package is Package legacyPackage)
        {
            foreach (var import in legacyPackage.ImportMap)
            {
                imports.Add(new JObject
                {
                    ["classPackage"] = import.ClassPackage.Text,
                    ["className"] = import.ClassName.Text,
                    ["objectName"] = import.ObjectName.Text,
                    ["outerIndex"] = import.OuterIndex?.Index ?? 0,
                    ["resolved"] = import.OuterIndex?.ResolvedObject?.ToString()
                });
            }
        }

        var sourceNames = new JArray();
        foreach (var entry in package.NameMap)
        {
            sourceNames.Add(entry.Name);
        }

        packageRows.Add(new JObject
        {
            ["packagePath"] = logicalPath,
            ["resolvedPackagePath"] = resolved,
            ["exportMapLength"] = package.ExportMapLength,
            ["importMapLength"] = package.ImportMapLength,
            ["dumpedExportCount"] = exports.Count,
            ["imports"] = imports,
            ["sourceNames"] = sourceNames,
            ["exports"] = exports
        });
    }
    catch (Exception e)
    {
        packageFailures.Add(new JObject
        {
            ["packagePath"] = logicalPath,
            ["resolvedPackagePath"] = resolved,
            ["error"] = e.GetType().FullName + ": " + e.Message
        });
    }
}

var output = new JObject
{
    ["schemaVersion"] = 1,
    ["sourceGame"] = sourceGameName,
    ["mappingTypes"] = provider.MappingsForGame?.Types.Count ?? 0,
    ["mappingEnums"] = provider.MappingsForGame?.Enums.Count ?? 0,
    ["requestedPackageCount"] = targets.Length,
    ["packageSuccessCount"] = packageRows.Count,
    ["packageFailureCount"] = packageFailures.Count,
    ["totalExportsInPackages"] = totalExports,
    ["dumpedExports"] = dumpedExports,
    ["dumpedProperties"] = dumpedProperties,
    ["dumpedFunctionsWithBytecode"] = dumpedFunctions,
    ["packages"] = packageRows,
    ["packageFailures"] = packageFailures,
    ["bytecodeAvailable"] = dumpedFunctions > 0,
    ["ready"] = packageFailures.Count == 0 &&
                packageRows.Count == targets.Length &&
                dumpedExports > 0 &&
                dumpedProperties > 0
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(outputPath, output.ToString(Formatting.Indented));

Console.WriteLine(
    "XZOGOT_NUKETOWN_GAMEPLAY_TRUTH " +
    new JObject
    {
        ["packages"] = packageRows.Count,
        ["failures"] = packageFailures.Count,
        ["exports"] = dumpedExports,
        ["properties"] = dumpedProperties,
        ["functions"] = dumpedFunctions,
        ["ready"] = output["ready"]
    }.ToString(Formatting.None));

if (output["ready"]?.Value<bool>() != true)
{
    Console.WriteLine("XZOGOT_NUKETOWN_GAMEPLAY_TRUTH_FAILURE");
    return 5;
}

Console.WriteLine("XZOGOT_NUKETOWN_GAMEPLAY_TRUTH_GREEN");
return 0;

static JToken SafeToken(
    object? value,
    Newtonsoft.Json.JsonSerializer serializer)
{
    if (value is null)
        return JValue.CreateNull();

    try
    {
        return JToken.FromObject(value, serializer);
    }
    catch (Exception e)
    {
        return new JObject
        {
            ["fallbackType"] = value.GetType().FullName,
            ["fallbackText"] = value.ToString(),
            ["serializationError"] = e.GetType().Name + ": " + e.Message
        };
    }
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    if (provider.TryGetGameFile(logicalPath, out _))
        return logicalPath;

    var normalized = logicalPath.Replace('\\', '/');

    return provider.Files.Keys.FirstOrDefault(
        key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase));
}
