using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Objects.Engine;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEAudioSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    return Regex.Replace(
        path,
        @"^shard-\d+/",
        "",
        RegexOptions.IgnoreCase);
}

string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized = NormalizeMergedShardPath(logicalPath);

    foreach (var file in provider.Files.Values)
    {
        var candidate = file.Path.Replace('\\', '/');
        if (candidate.Equals(
                normalized,
                StringComparison.OrdinalIgnoreCase) ||
            candidate.EndsWith(
                "/" + normalized,
                StringComparison.OrdinalIgnoreCase))
        {
            return file.Path;
        }
    }

    return null;
}

List<object> BuildHierarchy(USceneComponent start)
{
    var rows = new List<object>();
    var seen = new HashSet<string>(StringComparer.Ordinal);
    USceneComponent? current = start;

    for (var depth = 0;
         current is not null && depth < 64;
         ++depth)
    {
        var path = current.GetPathName();
        if (!seen.Add(path))
            throw new InvalidOperationException(
                "audio component attachment cycle: " + path);

        var location = current.GetRelativeLocation();
        var rotation = current.GetRelativeRotation();
        var scale = current.GetRelativeScale3D();

        rows.Add(new
        {
            depth,
            objectPath = path,
            componentName = current.Name,
            locationUEcm = new {
                X = location.X,
                Y = location.Y,
                Z = location.Z
            },
            rotationUE = new {
                Pitch = rotation.Pitch,
                Yaw = rotation.Yaw,
                Roll = rotation.Roll
            },
            scale = new {
                X = scale.X,
                Y = scale.Y,
                Z = scale.Z
            }
        });

        USceneComponent? parent = null;
        try
        {
            var attach = current.AttachParent;
            if (attach is { IsNull: false })
                attach.TryLoad<USceneComponent>(out parent);
        }
        catch
        {
            parent = null;
        }
        current = parent;
    }

    if (rows.Count == 0)
        throw new InvalidOperationException(
            "empty audio component hierarchy");

    return rows;
}

string? ReferencePath(FPackageIndex index)
{
    if (index.IsNull)
        return null;

    return index.ResolvedObject?.GetPathName()
        ?? index.Name;
}


(USoundBase? loaded, FPackageIndex? index, string? provenance) TryResolveSound(
    UAudioComponent candidate,
    string provenance)
{
    if (candidate.Sound is not null)
        return (candidate.Sound, null, provenance + ":typed");

    try
    {
        var index = candidate.GetOrDefault<FPackageIndex?>("Sound");
        if (index is { IsNull: false })
            return (null, index, provenance + ":property");
    }
    catch
    {
        // Keep walking cooked Blueprint templates.
    }

    return (null, null, null);
}

UBlueprintGeneratedClass? ResolveGeneratedClassByExportType(
    DefaultFileProvider provider,
    string actorExportType)
{
    if (string.IsNullOrWhiteSpace(actorExportType) ||
        !actorExportType.EndsWith("_C", StringComparison.Ordinal))
        return null;

    var assetBase = actorExportType[..^2];
    var assetFile = assetBase + ".uasset";

    foreach (var file in provider.Files.Values
                 .Where(file => {
                     var p = file.Path.Replace('\\', '/');
                     return p.EndsWith(
                         "/" + assetFile,
                         StringComparison.OrdinalIgnoreCase) ||
                         p.Equals(assetFile, StringComparison.OrdinalIgnoreCase);
                 })
                 .OrderBy(file => file.Path, StringComparer.OrdinalIgnoreCase))
    {
        try
        {
            var package = provider.LoadPackage(file.Path);
            var generated = package.GetExports()
                .OfType<UBlueprintGeneratedClass>()
                .FirstOrDefault(x =>
                    x.Name.Equals(
                        actorExportType,
                        StringComparison.OrdinalIgnoreCase));
            if (generated is not null)
                return generated;
        }
        catch
        {
            // Try another package candidate with the same asset basename.
        }
    }

    return null;
}

(USoundBase? loaded, FPackageIndex? index, string? provenance)
ResolveBlueprintSoundTemplate(
    DefaultFileProvider provider,
    UAudioComponent component)
{
    var directTemplate =
        component.Template?.Object?.Value as UAudioComponent;
    if (directTemplate is not null)
    {
        var direct = TryResolveSound(
            directTemplate,
            "component_template:" + directTemplate.GetPathName());
        if (direct.loaded is not null || direct.index is not null)
            return direct;
    }

    UObject? owner = null;
    try
    {
        owner = component.Outer?.Object?.Value;
    }
    catch
    {
        owner = null;
    }

    while (owner is not null)
    {
        var generated =
            owner.Class?.Object?.Value as UBlueprintGeneratedClass;

        if (generated is null &&
            owner.ExportType.EndsWith("_C", StringComparison.Ordinal))
        {
            generated = ResolveGeneratedClassByExportType(
                provider,
                owner.ExportType);
        }

        if (generated is not null)
        {
            var seenClasses =
                new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            for (var current = generated;
                 current is not null &&
                 seenClasses.Add(current.GetPathName());
                 current =
                    current.Super?.Object?.Value
                        as UBlueprintGeneratedClass)
            {
                foreach (var templateIndex in current.ComponentTemplates)
                {
                    try
                    {
                        if (templateIndex is not { IsNull: false })
                            continue;
                        if (!templateIndex.TryLoad<UAudioComponent>(
                                out var template) ||
                            template is null)
                            continue;
                        if (!template.Name.Equals(
                                component.Name,
                                StringComparison.OrdinalIgnoreCase))
                            continue;

                        var resolved = TryResolveSound(
                            template,
                            "generated_class_component_template:" +
                            template.GetPathName());
                        if (resolved.loaded is not null ||
                            resolved.index is not null)
                            return resolved;
                    }
                    catch
                    {
                        // Keep searching other template authorities.
                    }
                }

                try
                {
                    if (current.SimpleConstructionScript
                        is { IsNull: false } scsIndex &&
                        scsIndex.TryLoad<USimpleConstructionScript>(
                            out var scs) &&
                        scs is not null)
                    {
                        foreach (var node in
                                 scs.GetAllNodesRecursive())
                        {
                            if (!node.InternalVariableName.Text.Equals(
                                    component.Name,
                                    StringComparison.OrdinalIgnoreCase))
                                continue;

                            var template =
                                node.GetComponentTemplate()
                                    as UAudioComponent;
                            if (template is null)
                                continue;

                            var resolved = TryResolveSound(
                                template,
                                "scs_component_template:" +
                                template.GetPathName());
                            if (resolved.loaded is not null ||
                                resolved.index is not null)
                                return resolved;
                        }
                    }
                }
                catch
                {
                    // Cooked SCS can be partial; continue to overrides.
                }

                try
                {
                    if (current.InheritableComponentHandler
                        is { IsNull: false } handlerIndex &&
                        handlerIndex.TryLoad<
                            UInheritableComponentHandler>(
                                out var handler) &&
                        handler is not null)
                    {
                        foreach (var record in handler.GetRecords())
                        {
                            if (!record.ComponentKey
                                .SCSVariableName.Text.Equals(
                                    component.Name,
                                    StringComparison.OrdinalIgnoreCase))
                                continue;
                            var templateIndex =
                                record.ComponentTemplate;
                            if (templateIndex
                                is not { IsNull: false })
                                continue;
                            if (!templateIndex.TryLoad<
                                    UAudioComponent>(
                                        out var template) ||
                                template is null)
                                continue;

                            var resolved = TryResolveSound(
                                template,
                                "inheritable_component_template:" +
                                template.GetPathName());
                            if (resolved.loaded is not null ||
                                resolved.index is not null)
                                return resolved;
                        }
                    }
                }
                catch
                {
                    // No usable cooked override in this class.
                }
            }
        }

        try
        {
            owner = owner.Outer?.Object?.Value;
        }
        catch
        {
            owner = null;
        }
    }

    return (null, null, null);
}


object[] DescribeOwnerResolutionChain(UAudioComponent component)
{
    var rows = new List<object>();
    UObject? current = component;
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    for (var depth = 0; current is not null && depth < 16; ++depth)
    {
        var path = current.GetPathName();
        if (!seen.Add(path))
            break;

        string? classPath = null;
        string? classType = null;
        string? templatePath = null;
        string? templateType = null;

        try
        {
            var cls = current.Class?.Object?.Value;
            classPath = cls?.GetPathName();
            classType = cls?.ExportType;
        }
        catch { }

        try
        {
            var template = current.Template?.Object?.Value;
            templatePath = template?.GetPathName();
            templateType = template?.ExportType;
        }
        catch { }

        rows.Add(new
        {
            depth,
            objectPath = path,
            exportType = current.ExportType,
            objectType = current.GetType().FullName,
            classPath,
            classType,
            templatePath,
            templateType
        });

        try
        {
            current = current.Outer?.Object?.Value;
        }
        catch
        {
            current = null;
        }
    }

    return rows.ToArray();
}

using var censusDoc =
    JsonDocument.Parse(
        File.ReadAllText(censusPath));

var mapPackages =
    censusDoc.RootElement
        .GetProperty("packages")
        .EnumerateArray()
        .Select(row =>
            NormalizeMergedShardPath(
                row.GetProperty("packagePath").GetString()
                ?? throw new InvalidDataException(
                    "packagePath missing")))
        .Where(path =>
            path.EndsWith(
                ".umap",
                StringComparison.OrdinalIgnoreCase))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
        .ToArray();

if (mapPackages.Length == 0)
    throw new InvalidDataException(
        "no .umap packages in source census");

var provider =
    new DefaultFileProvider(
        root,
        SearchOption.AllDirectories,
        new VersionContainer(sourceGame),
        StringComparer.OrdinalIgnoreCase)
    {
        MappingsContainer =
            new FileUsmapTypeMappingsProvider(
                mappingsPath)
    };

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

// Nacht's cooked Blueprint instances intentionally omit AudioComponent.Sound
// when the authoritative value lives on the component archetype/template.
// Match the proven static-mesh resolver: resolve inherited defaults before
// loading the UMAP instead of treating omitted instance properties as null.
PropertyUtil.SearchPropertyInTemplate = true;

var rows = new List<object>();
var packageFailures = new List<object>();
var componentFailures = new List<object>();
var packagesLoaded = 0;
var nullSoundCount = 0;
var loadedSoundCount = 0;
var referencedSoundCount = 0;
var soundTypeCounts =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);

foreach (var logicalPackage in mapPackages)
{
    var resolved =
        ResolveProviderPackagePath(
            provider,
            logicalPackage);

    if (resolved is null)
    {
        packageFailures.Add(new {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        var components = package.GetExports()
            .OfType<UAudioComponent>()
            .OrderBy(
                component => component.GetPathName(),
                StringComparer.Ordinal)
            .ToArray();

        foreach (var component in components)
        {
            try
            {
            var sound = component.Sound;
            string? soundObjectPath = null;
            string? soundExportType = null;
            string? rawSoundReference = null;
            string? soundProvenance = null;
            var soundLoaded = false;

            if (sound is not null)
            {
                soundObjectPath = sound.GetPathName();
                soundExportType = sound.ExportType;
                rawSoundReference = soundObjectPath;
                soundProvenance = "instance:typed";
                soundLoaded = true;
                loadedSoundCount++;
                referencedSoundCount++;
            }
            else
            {
                FPackageIndex? soundIndex = null;
                try
                {
                    soundIndex = component.GetOrDefault<FPackageIndex?>("Sound");
                }
                catch
                {
                    soundIndex = null;
                }
                if (soundIndex is { IsNull: false })
                {
                    rawSoundReference = soundIndex.ToString();
                    soundObjectPath =
                        ReferencePath(soundIndex);
                    soundExportType =
                        soundIndex.ResolvedObject?.Object?.Value
                            ?.ExportType;
                    soundProvenance = "instance:property";
                    referencedSoundCount++;
                }
                else
                {
                    var inherited =
                        ResolveBlueprintSoundTemplate(provider, component);
                    if (inherited.loaded is not null)
                    {
                        soundObjectPath =
                            inherited.loaded.GetPathName();
                        soundExportType =
                            inherited.loaded.ExportType;
                        rawSoundReference = soundObjectPath;
                        soundProvenance =
                            inherited.provenance;
                        soundLoaded = true;
                        loadedSoundCount++;
                        referencedSoundCount++;
                    }
                    else if (inherited.index
                             is { IsNull: false })
                    {
                        rawSoundReference =
                            inherited.index.ToString();
                        soundObjectPath =
                            ReferencePath(inherited.index);
                        soundExportType =
                            inherited.index.ResolvedObject
                                ?.Object?.Value?.ExportType;
                        soundProvenance =
                            inherited.provenance;
                        referencedSoundCount++;
                    }
                    else
                    {
                        nullSoundCount++;
                    }
                }
            }

            var typeKey =
                string.IsNullOrWhiteSpace(soundExportType)
                    ? (soundObjectPath is null
                        ? "null"
                        : "unloaded_reference")
                    : soundExportType!;
            soundTypeCounts[typeKey] =
                soundTypeCounts.TryGetValue(
                    typeKey,
                    out var oldCount)
                    ? oldCount + 1
                    : 1;

            FPackageIndex? attenuation = null;
            try
            {
                attenuation =
                    component.GetOrDefault<FPackageIndex?>(
                        "AttenuationSettings");
            }
            catch
            {
                attenuation = null;
            }

            var path = component.GetPathName();
            var lastDot = path.LastIndexOf('.');
            var parentPath =
                lastDot > 0
                    ? path[..lastDot]
                    : "";
            var parentName =
                parentPath.Length > 0
                    ? parentPath.Split('.').Last()
                    : "";

            rows.Add(new
            {
                id = $"audio_{rows.Count:0000}",
                packagePath = logicalPackage,
                actorName = parentName,
                componentName = component.Name,
                sourcePath = path,
                hierarchy = BuildHierarchy(component),
                ownerResolutionChain = DescribeOwnerResolutionChain(component),
                sound = new {
                    objectPath = soundObjectPath,
                    exportType = soundExportType,
                    loaded = soundLoaded,
                    reference = rawSoundReference,
                    provenance = soundProvenance
                },
                properties = new {
                    volumeMultiplier =
                        component.GetOrDefault<float>(
                            "VolumeMultiplier",
                            1.0f),
                    pitchMultiplier =
                        component.GetOrDefault<float>(
                            "PitchMultiplier",
                            1.0f),
                    autoActivate =
                        component.GetOrDefault<bool>(
                            "bAutoActivate",
                            true),
                    allowSpatialization =
                        component.GetOrDefault<bool>(
                            "bAllowSpatialization",
                            true),
                    isUISound =
                        component.GetOrDefault<bool>(
                            "bIsUISound",
                            false),
                    stopWhenOwnerDestroyed =
                        component.GetOrDefault<bool>(
                            "bStopWhenOwnerDestroyed",
                            false),
                    overrideAttenuation =
                        component.GetOrDefault<bool>(
                            "bOverrideAttenuation",
                            false),
                    suppressSubtitles =
                        component.GetOrDefault<bool>(
                            "bSuppressSubtitles",
                            false),
                    attenuationSettings =
                        attenuation is null
                            ? null
                            : ReferencePath(attenuation)
                }
            });
            }
            catch (Exception componentError)
            {
                componentFailures.Add(new {
                    packagePath = logicalPackage,
                    componentPath = component.GetPathName(),
                    error =
                        componentError.GetType().Name + ": " +
                        componentError.Message
                });
            }
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new {
            packagePath = logicalPackage,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    packagesLoaded == mapPackages.Length &&
    packageFailures.Count == 0 &&
    componentFailures.Count == 0;


foreach (var row in rows.Where(row =>
             row.GetType().GetProperty("sound") is not null))
{
    // Structured per-row diagnostics are persisted in JSON. Console summary
    // below is generated from the source components to make fast-gate triage
    // possible without downloading the artifact.
}

foreach (var component in rows.Select((value, index) => new { value, index }))
{
    var json = JsonSerializer.Serialize(component.value);
    if (json.Contains("\"objectPath\":null", StringComparison.Ordinal))
    {
        Console.WriteLine(
            "XZIEL_UE_AUDIO_SCENE_NULL_SOUND_DIAG " + json);
    }
}

var output = new {
    schemaVersion = 1,
    sourceGame = sourceGameName,
    coordinateSystem = new {
        source = "Unreal Engine centimeters",
        target = "XZIEL meters X,-Y,Z",
        hierarchyConvention =
            "component local transforms ordered child-to-parent"
    },
    mapPackageCount = mapPackages.Length,
    packagesLoaded,
    audioComponentCount = rows.Count,
    referencedSoundCount,
    loadedSoundCount,
    nullSoundCount,
    soundTypeCounts,
    audioComponents = rows,
    packageFailures,
    componentFailures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(outputPath))!);

File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_UE_AUDIO_SCENE_EXTRACT " +
    JsonSerializer.Serialize(new {
        output.mapPackageCount,
        output.packagesLoaded,
        output.audioComponentCount,
        output.referencedSoundCount,
        output.loadedSoundCount,
        output.nullSoundCount,
        output.soundTypeCounts,
        packageFailureCount = packageFailures.Count,
        componentFailureCount = componentFailures.Count,
        output.ready
    }));

foreach (var failure in packageFailures.Take(20))
{
    Console.WriteLine(
        "XZIEL_UE_AUDIO_SCENE_PACKAGE_FAILURE " +
        JsonSerializer.Serialize(failure));
}

foreach (var failure in componentFailures.Take(40))
{
    Console.WriteLine(
        "XZIEL_UE_AUDIO_SCENE_COMPONENT_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_AUDIO_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_AUDIO_SCENE_EXTRACT_GREEN");
return 0;
