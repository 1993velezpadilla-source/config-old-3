using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Sound;
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
            var soundLoaded = false;

            if (sound is not null)
            {
                soundObjectPath = sound.GetPathName();
                soundExportType = sound.ExportType;
                rawSoundReference = soundObjectPath;
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
                    referencedSoundCount++;
                }
                else
                {
                    nullSoundCount++;
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
                sound = new {
                    objectPath = soundObjectPath,
                    exportType = soundExportType,
                    loaded = soundLoaded,
                    reference = rawSoundReference
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
