using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Objects.Engine;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEAudioTemplateCatalog <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];
var sourceGameName = args[4];

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException("unsupported source-game: " + sourceGameName)
    };

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    return Regex.Replace(path, @"^shard-\d+/", "", RegexOptions.IgnoreCase);
}

string? ResolveProviderPackagePath(DefaultFileProvider provider, string logicalPath)
{
    var normalized = NormalizeMergedShardPath(logicalPath);
    foreach (var file in provider.Files.Values)
    {
        var candidate = file.Path.Replace('\\', '/');
        if (candidate.Equals(normalized, StringComparison.OrdinalIgnoreCase) ||
            candidate.EndsWith("/" + normalized, StringComparison.OrdinalIgnoreCase))
            return file.Path;
    }
    return null;
}

string? ReferencePath(FPackageIndex index)
{
    if (index.IsNull) return null;
    return index.ResolvedObject?.GetPathName() ?? index.Name;
}

var targetNames = new HashSet<string>(
    new[] { "SoundMix", "PerkMachineHum", "PackaLoop" },
    StringComparer.OrdinalIgnoreCase);

var targetGeneratedClasses = new HashSet<string>(
    new[] { "Box5_C", "PerkMachine_QuickRevive_C", "PunchAPackMachine_C" },
    StringComparer.OrdinalIgnoreCase);

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var packages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Where(row => {
        if (!row.TryGetProperty("classes", out var classes)) return false;
        foreach (var cls in classes.EnumerateObject())
        {
            if (cls.Value.ValueKind == JsonValueKind.Number &&
                cls.Value.GetInt32() > 0 &&
                (cls.Name.Contains("AudioComponent", StringComparison.OrdinalIgnoreCase) ||
                 cls.Name.Contains("BlueprintGeneratedClass", StringComparison.OrdinalIgnoreCase)))
                return true;
        }
        return false;
    })
    .Select(row => NormalizeMergedShardPath(
        row.GetProperty("packagePath").GetString()
        ?? throw new InvalidDataException("packagePath missing")))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
    .ToArray();

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer = new FileUsmapTypeMappingsProvider(mappingsPath)
};
provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var matches = new List<object>();
var blueprintMatches = new List<object>();
var packageFailures = new List<object>();
var packagesLoaded = 0;
var audioComponentsSeen = 0;

object DescribeAudioComponent(
    string packagePath,
    string authority,
    UAudioComponent component)
{
    USoundBase? sound = component.Sound;
    FPackageIndex? soundIndex = null;
    if (sound is null)
    {
        try
        {
            soundIndex = component.GetOrDefault<FPackageIndex?>("Sound");
        }
        catch
        {
            soundIndex = null;
        }
    }

    var soundPath = sound?.GetPathName();
    var soundType = sound?.ExportType;
    var loaded = sound is not null;

    if (sound is null && soundIndex is { IsNull: false })
    {
        soundPath = ReferencePath(soundIndex);
        soundType = soundIndex.ResolvedObject?.Class?.Name.Text
            ?? soundIndex.ResolvedObject?.Object?.Value?.ExportType;
    }

    return new {
        packagePath,
        authority,
        componentName = component.Name,
        objectPath = component.GetPathName(),
        exportType = component.ExportType,
        outerPath = component.Outer?.GetPathName(),
        classPath = component.Class?.GetPathName(),
        templatePath = component.Template?.GetPathName(),
        flags = component.Flags.ToString(),
        sound = new {
            objectPath = soundPath,
            exportType = soundType,
            loaded,
            reference = soundIndex is { IsNull: false } ? soundIndex.ToString() : null
        },
        propertyNames = component.Properties
            .Select(p => p.Name.Text)
            .OrderBy(x => x, StringComparer.Ordinal)
            .ToArray()
    };
}

foreach (var logical in packages)
{
    var resolved = ResolveProviderPackagePath(provider, logical);
    if (resolved is null)
    {
        packageFailures.Add(new { packagePath = logical, error = "provider path unresolved" });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        foreach (var component in package.GetExports()
                     .OfType<UAudioComponent>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            audioComponentsSeen++;
            if (!targetNames.Contains(component.Name))
                continue;

            matches.Add(DescribeAudioComponent(logical, "package_export", component));
        }

        foreach (var generated in package.GetExports()
                     .OfType<UBlueprintGeneratedClass>()
                     .Where(x => targetGeneratedClasses.Contains(x.Name))
                     .OrderBy(x => x.Name, StringComparer.OrdinalIgnoreCase))
        {
            var authorities = new List<object>();

            foreach (var templateRef in generated.ComponentTemplates)
            {
                try
                {
                    if (templateRef is { IsNull: false } &&
                        templateRef.TryLoad<UAudioComponent>(out var template) &&
                        template is not null &&
                        targetNames.Contains(template.Name))
                    {
                        authorities.Add(
                            DescribeAudioComponent(
                                logical,
                                "generated_class_component_template",
                                template));
                    }
                }
                catch { }
            }

            try
            {
                if (generated.SimpleConstructionScript is { IsNull: false } scsRef &&
                    scsRef.TryLoad<USimpleConstructionScript>(out var scs) &&
                    scs is not null)
                {
                    foreach (var node in scs.GetAllNodesRecursive())
                    {
                        if (!targetNames.Contains(node.InternalVariableName.Text))
                            continue;

                        var template = node.GetComponentTemplate() as UAudioComponent;
                        if (template is not null)
                        {
                            authorities.Add(
                                DescribeAudioComponent(
                                    logical,
                                    "scs_component_template",
                                    template));
                        }
                    }
                }
            }
            catch { }

            try
            {
                if (generated.InheritableComponentHandler is { IsNull: false } handlerRef &&
                    handlerRef.TryLoad<UInheritableComponentHandler>(out var handler) &&
                    handler is not null)
                {
                    foreach (var record in handler.GetRecords())
                    {
                        if (!targetNames.Contains(record.ComponentKey.SCSVariableName.Text))
                            continue;

                        if (record.ComponentTemplate is { IsNull: false } templateRef &&
                            templateRef.TryLoad<UAudioComponent>(out var template) &&
                            template is not null)
                        {
                            authorities.Add(
                                DescribeAudioComponent(
                                    logical,
                                    "inheritable_component_template",
                                    template));
                        }
                    }
                }
            }
            catch { }

            object? classDefaultObject = null;
            try
            {
                var cdo = generated.ClassDefaultObject.Load<CUE4Parse.UE4.Assets.Exports.UObject>();
                if (cdo is not null)
                {
                    classDefaultObject = new {
                        objectPath = cdo.GetPathName(),
                        exportType = cdo.ExportType,
                        propertyNames = cdo.Properties
                            .Select(p => p.Name.Text)
                            .OrderBy(x => x, StringComparer.Ordinal)
                            .ToArray()
                    };
                }
            }
            catch { }

            blueprintMatches.Add(new {
                packagePath = logical,
                generatedClass = generated.Name,
                generatedClassPath = generated.GetPathName(),
                componentTemplateCount = generated.ComponentTemplates.Length,
                simpleConstructionScript = generated.SimpleConstructionScript?.ToString(),
                inheritableComponentHandler = generated.InheritableComponentHandler?.ToString(),
                classDefaultObject,
                authorities
            });
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new {
            packagePath = logical,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var grouped = targetNames
    .OrderBy(x => x, StringComparer.Ordinal)
    .ToDictionary(
        name => name,
        name => matches.Count(row => {
            var prop = row.GetType().GetProperty("componentName");
            return string.Equals(
                prop?.GetValue(row)?.ToString(),
                name,
                StringComparison.OrdinalIgnoreCase);
        }),
        StringComparer.OrdinalIgnoreCase);

var output = new {
    schemaVersion = 1,
    sourceGame = sourceGameName,
    candidatePackageCount = packages.Length,
    packagesLoaded,
    audioComponentsSeen,
    targetNames = targetNames.OrderBy(x => x).ToArray(),
    targetMatchCount = matches.Count,
    targetCounts = grouped,
    targetGeneratedClasses = targetGeneratedClasses.OrderBy(x => x).ToArray(),
    blueprintMatchCount = blueprintMatches.Count,
    blueprintMatches,
    matches,
    packageFailures,
    ready = packages.Length > 0 && packagesLoaded == packages.Length && packageFailures.Count == 0
};

Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(output, new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine("XZIEL_UE_AUDIO_TEMPLATE_CATALOG " + JsonSerializer.Serialize(new {
    output.candidatePackageCount,
    output.packagesLoaded,
    output.audioComponentsSeen,
    output.targetMatchCount,
    output.targetCounts,
    output.blueprintMatchCount,
    failureCount = packageFailures.Count,
    output.ready
}));

foreach (var row in matches)
    Console.WriteLine("XZIEL_UE_AUDIO_TEMPLATE_MATCH " + JsonSerializer.Serialize(row));

foreach (var row in blueprintMatches)
    Console.WriteLine("XZIEL_UE_AUDIO_BLUEPRINT_MATCH " + JsonSerializer.Serialize(row));

foreach (var failure in packageFailures.Take(20))
    Console.WriteLine("XZIEL_UE_AUDIO_TEMPLATE_PACKAGE_FAILURE " + JsonSerializer.Serialize(failure));

if (!output.ready)
{
    Console.WriteLine("XZIEL_UE_AUDIO_TEMPLATE_CATALOG_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_AUDIO_TEMPLATE_CATALOG_GREEN");
return 0;
