using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Component.Atmosphere;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Collections;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEEnvironmentSceneExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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
                "environment component attachment cycle: " + path);

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

        current = current.GetAttachParent();
    }

    if (rows.Count == 0)
        throw new InvalidOperationException(
            "empty environment component hierarchy");

    return rows;
}

object? DescribeDiagnosticValue(
    object? value,
    int depth = 0)
{
    if (value is null)
        return null;

    if (depth >= 4)
        return value.ToString();

    if (value is FPackageIndex packageIndex)
    {
        return new
        {
            kind = "FPackageIndex",
            index = packageIndex.Index,
            path =
                packageIndex.ResolvedObject?.GetPathName()
                ?? packageIndex.ToString()
        };
    }

    if (value is FStructFallback fallback)
    {
        return new
        {
            kind = "FStructFallback",
            properties = fallback.Properties
                .Select(property => new
                {
                    name = property.Name.Text,
                    valueType =
                        property.Tag?.GenericValue?
                            .GetType().FullName,
                    value =
                        DescribeDiagnosticValue(
                            property.Tag?.GenericValue,
                            depth + 1)
                })
                .ToArray()
        };
    }

    if (value is IEnumerable enumerable &&
        value is not string)
    {
        var values = new List<object?>();
        foreach (var item in enumerable)
        {
            if (values.Count >= 256)
                break;
            values.Add(
                DescribeDiagnosticValue(
                    item,
                    depth + 1));
        }
        return values.ToArray();
    }

    var type = value.GetType();
    if (type.IsPrimitive ||
        value is decimal ||
        value is string ||
        value is Enum)
    {
        return value;
    }

    return value.ToString();
}

object[] DescribeProperties(
    IEnumerable<CUE4Parse.UE4.Assets.Objects.FPropertyTag> props)
{
    return props
        .OrderBy(p => p.Name.Text, StringComparer.Ordinal)
        .Select(property => (object)new
        {
            name = property.Name.Text,
            valueType =
                property.Tag?.GenericValue?
                    .GetType().FullName,
            value =
                DescribeDiagnosticValue(
                    property.Tag?.GenericValue)
        })
        .ToArray();
}

string Kind(USceneComponent component)
{
    if (component is UExponentialHeightFogComponent)
        return "exponential_height_fog";
    if (component is UAtmosphericFogComponent)
        return "atmospheric_fog";
    if (component is USkyAtmosphereComponent)
        return "sky_atmosphere";
    if (component is UReflectionCaptureComponent)
        return "reflection_capture";
    if (component is UPostProcessComponent)
        return "post_process";
    return "";
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

var provider = new DefaultFileProvider(
    root,
    SearchOption.AllDirectories,
    new VersionContainer(sourceGame),
    StringComparer.OrdinalIgnoreCase)
{
    MappingsContainer =
        new FileUsmapTypeMappingsProvider(mappingsPath)
};

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var rows = new List<object>();
var counts =
    new SortedDictionary<string, int>(
        StringComparer.Ordinal);
var packageFailures = new List<object>();
var packagesLoaded = 0;

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

        foreach (var component in package.GetExports()
                     .OfType<USceneComponent>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            var kind = Kind(component);
            if (kind.Length == 0)
                continue;

            counts[kind] =
                counts.GetValueOrDefault(kind) + 1;

            object typed;
            if (component is UExponentialHeightFogComponent fog)
            {
                typed = new {
                    fogDensity = fog.FogDensity,
                    fogHeightFalloff = fog.FogHeightFalloff,
                    fogMaxOpacity = fog.FogMaxOpacity,
                    startDistanceCm = fog.StartDistance,
                    fogInscatteringLuminance =
                        fog.FogInscatteringLuminance.ToString(),
                    directionalInscatteringLuminance =
                        fog.DirectionalInscatteringLuminance.ToString(),
                    directionalInscatteringExponent =
                        fog.DirectionalInscatteringExponent,
                    directionalInscatteringStartDistanceCm =
                        fog.DirectionalInscatteringStartDistance
                };
            }
            else if (component is UAtmosphericFogComponent atmospheric)
            {
                typed = new {
                    transformMode = atmospheric.TransformMode.ToString(),
                    bottomRadiusKm = atmospheric.BottomRadius,
                    atmosphereHeightKm = atmospheric.AtmosphereHeight,
                    rayleighScatteringScale =
                        atmospheric.RayleighScatteringScale,
                    rayleighScattering =
                        atmospheric.RayleighScattering.ToString(),
                    rayleighDistributionKm =
                        atmospheric.RayleighExponentialDistribution,
                    mieScatteringScale =
                        atmospheric.MieScatteringScale,
                    mieScattering =
                        atmospheric.MieScattering.ToString(),
                    mieAbsorptionScale =
                        atmospheric.MieAbsorptionScale,
                    mieAbsorption =
                        atmospheric.MieAbsorption.ToString(),
                    mieAnisotropy =
                        atmospheric.MieAnisotropy,
                    mieDistributionKm =
                        atmospheric.MieExponentialDistribution,
                    skyLuminanceFactor =
                        atmospheric.SkyLuminanceFactor.ToString()
                };
            }
            else if (component is USkyAtmosphereComponent sky)
            {
                typed = new {
                    transformMode = sky.TransformMode.ToString(),
                    bottomRadiusKm = sky.BottomRadius,
                    atmosphereHeightKm = sky.AtmosphereHeight,
                    rayleighScatteringScale =
                        sky.RayleighScatteringScale,
                    rayleighScattering =
                        sky.RayleighScattering.ToString(),
                    rayleighDistributionKm =
                        sky.RayleighExponentialDistribution,
                    mieScatteringScale =
                        sky.MieScatteringScale,
                    mieScattering =
                        sky.MieScattering.ToString(),
                    mieAbsorptionScale =
                        sky.MieAbsorptionScale,
                    mieAbsorption =
                        sky.MieAbsorption.ToString(),
                    mieAnisotropy =
                        sky.MieAnisotropy,
                    mieDistributionKm =
                        sky.MieExponentialDistribution,
                    skyLuminanceFactor =
                        sky.SkyLuminanceFactor.ToString()
                };
            }
            else if (component is UReflectionCaptureComponent reflection)
            {
                typed = new {
                    averageBrightness =
                        reflection.AverageBrightness,
                    legacy = reflection.bLegacy,
                    legacyCubemapSize =
                        reflection.LegacyMapBuildData?
                            .CubemapSize,
                    legacyAverageBrightness =
                        reflection.LegacyMapBuildData?
                            .AverageBrightness
                };
            }
            else
            {
                typed = new { };
            }

            rows.Add(new
            {
                id = $"environment_{rows.Count:0000}",
                packagePath = logicalPackage,
                componentType = kind,
                sourceType = component.ExportType,
                sourcePath = component.GetPathName(),
                hierarchy = BuildHierarchy(component),
                typed,
                rawProperties =
                    DescribeProperties(component.Properties)
            });
        }
    }
    catch (Exception ex)
    {
        packageFailures.Add(new
        {
            packagePath = logicalPackage,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    packagesLoaded == mapPackages.Length &&
    packageFailures.Count == 0;

var output = new
{
    schemaVersion = 1,
    sourceGame = sourceGameName,
    coordinateSystem = new
    {
        source = "Unreal Engine centimeters",
        target = "XZIEL meters X,-Y,Z",
        hierarchyConvention =
            "component local transforms ordered child-to-parent"
    },
    mapPackageCount = mapPackages.Length,
    packagesLoaded,
    environmentComponentCount = rows.Count,
    typeCounts = counts,
    components = rows,
    packageFailures,
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
    "XZIEL_UE_ENVIRONMENT_SCENE_EXTRACT " +
    JsonSerializer.Serialize(new {
        output.mapPackageCount,
        output.packagesLoaded,
        output.environmentComponentCount,
        output.typeCounts,
        failureCount = packageFailures.Count,
        output.ready
    }));

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_ENVIRONMENT_SCENE_EXTRACT_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_ENVIRONMENT_SCENE_EXTRACT_GREEN");
return 0;
