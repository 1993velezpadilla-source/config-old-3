using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UELightExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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

const BindingFlags Flags =
    BindingFlags.Instance |
    BindingFlags.Public |
    BindingFlags.NonPublic;

object? ReadMember(object target, string name)
{
    var type = target.GetType();

    var field = type.GetField(name, Flags);
    if (field is not null)
    {
        try { return field.GetValue(target); }
        catch { }
    }

    var property = type.GetProperty(name, Flags);
    if (
        property is not null &&
        property.GetIndexParameters().Length == 0 &&
        property.GetMethod is not null)
    {
        try { return property.GetValue(target); }
        catch { }
    }

    try
    {
        var method = type.GetMethods(Flags)
            .FirstOrDefault(m =>
                m.Name == "GetOrDefault" &&
                m.IsGenericMethodDefinition &&
                m.GetParameters().Length >= 1);
        if (method is not null)
        {
            var generic = method.MakeGenericMethod(typeof(object));
            return generic.Invoke(target, new object?[] { name });
        }
    }
    catch { }

    return null;
}

double? Number(object? value)
{
    if (value is null)
        return null;

    try
    {
        return Convert.ToDouble(
            value,
            System.Globalization.CultureInfo.InvariantCulture);
    }
    catch
    {
        return null;
    }
}

bool? Boolean(object? value)
{
    if (value is bool b)
        return b;

    if (
        value is not null &&
        bool.TryParse(value.ToString(), out var parsed))
        return parsed;

    return null;
}

string? Text(object? value)
{
    if (value is null)
        return null;

    var text = value.ToString();
    return string.IsNullOrWhiteSpace(text)
        ? null
        : text;
}

Dictionary<string, double>? Vector(
    object? value,
    string[] names)
{
    if (value is null)
        return null;

    var result =
        new Dictionary<string, double>(
            StringComparer.Ordinal);

    foreach (var name in names)
    {
        var number =
            Number(ReadMember(value, name));

        if (number is null)
            return null;

        result[name] = number.Value;
    }

    return result;
}

Dictionary<string, int>? Color(object? value)
{
    if (value is null)
        return null;

    var result =
        new Dictionary<string, int>(
            StringComparer.Ordinal);

    var complete = true;
    foreach (var name in new[] { "R", "G", "B", "A" })
    {
        var number =
            Number(ReadMember(value, name));

        if (number is null)
        {
            complete = false;
            break;
        }

        result[name] =
            Math.Clamp(
                (int)Math.Round(number.Value),
                0,
                255);
    }

    if (complete)
        return result;

    var text =
        (value.ToString() ?? "")
            .Trim()
            .TrimStart('#');

    if (
        text.Length == 6 &&
        int.TryParse(
            text,
            System.Globalization.NumberStyles.HexNumber,
            null,
            out var rgb))
    {
        return new Dictionary<string, int> {
            ["R"] = (rgb >> 16) & 0xff,
            ["G"] = (rgb >> 8) & 0xff,
            ["B"] = rgb & 0xff,
            ["A"] = 255
        };
    }

    if (
        text.Length == 8 &&
        uint.TryParse(
            text,
            System.Globalization.NumberStyles.HexNumber,
            null,
            out var rgba))
    {
        return new Dictionary<string, int> {
            ["R"] = (int)((rgba >> 24) & 0xff),
            ["G"] = (int)((rgba >> 16) & 0xff),
            ["B"] = (int)((rgba >> 8) & 0xff),
            ["A"] = (int)(rgba & 0xff)
        };
    }

    return null;
}

object? ResolveAttachParent(object current)
{
    var attach =
        ReadMember(current, "AttachParent");

    if (
        attach is FPackageIndex packageIndex &&
        packageIndex.TryLoad<USceneComponent>(
            out var parent) &&
        parent is not null)
    {
        return parent;
    }

    return null;
}

List<object> BuildHierarchy(object start)
{
    var rows = new List<object>();
    var seen =
        new HashSet<object>(
            ReferenceEqualityComparer.Instance);

    object? current = start;

    for (
        var depth = 0;
        current is not null && depth < 64;
        ++depth)
    {
        if (!seen.Add(current))
            throw new InvalidOperationException(
                "attachment cycle");

        var location =
            Vector(
                ReadMember(
                    current,
                    "RelativeLocation"),
                new[] { "X", "Y", "Z" });

        var rotation =
            Vector(
                ReadMember(
                    current,
                    "RelativeRotation"),
                new[] { "Pitch", "Yaw", "Roll" });

        var scale =
            Vector(
                ReadMember(
                    current,
                    "RelativeScale3D"),
                new[] { "X", "Y", "Z" });

        if (
            location is null ||
            rotation is null ||
            scale is null)
        {
            throw new InvalidOperationException(
                "component transform incomplete");
        }

        rows.Add(new {
            depth,
            name =
                Text(ReadMember(current, "Name"))
                ?? current.GetType().Name,
            type =
                current.GetType().FullName
                ?? current.GetType().Name,
            locationUEcm = location,
            rotationUE = rotation,
            scale
        });

        current =
            ResolveAttachParent(current);
    }

    if (rows.Count == 0)
        throw new InvalidOperationException(
            "empty attachment chain");

    return rows;
}

string Kind(string fullType)
{
    if (fullType.EndsWith(
            ".UPointLightComponent",
            StringComparison.Ordinal))
        return "point";

    if (fullType.EndsWith(
            ".USpotLightComponent",
            StringComparison.Ordinal))
        return "spot";

    if (fullType.EndsWith(
            ".UDirectionalLightComponent",
            StringComparison.Ordinal))
        return "directional";

    if (fullType.EndsWith(
            ".USkyLightComponent",
            StringComparison.Ordinal))
        return "sky";

    return "";
}

string NormalizeMergedShardPath(string value)
{
    var path = value.Replace('\\', '/');
    path = Regex.Replace(
        path,
        @"^shard-\d+/",
        "",
        RegexOptions.IgnoreCase);
    return path;
}

string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized =
        NormalizeMergedShardPath(logicalPath);

    foreach (var file in provider.Files.Values)
    {
        var candidate =
            file.Path.Replace('\\', '/');

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
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .OrderBy(
            path => path,
            StringComparer.OrdinalIgnoreCase)
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
        var exports =
            provider.LoadPackage(resolved)
                .GetExports()
                .ToArray();
        packagesLoaded++;

        foreach (var export in exports)
        {
            var fullType =
                export.GetType().FullName
                ?? export.GetType().Name;

            var kind = Kind(fullType);
            if (kind.Length == 0)
                continue;

            var hierarchy =
                BuildHierarchy(export);

            var intensity =
                Number(
                    ReadMember(
                        export,
                        "Intensity"));

            var lightColor =
                Color(
                    ReadMember(
                        export,
                        "LightColor"));

            var radius =
                Number(
                    ReadMember(
                        export,
                        "AttenuationRadius"));

            var innerCone =
                Number(
                    ReadMember(
                        export,
                        "InnerConeAngle"));

            var outerCone =
                Number(
                    ReadMember(
                        export,
                        "OuterConeAngle"));

            var units =
                Text(
                    ReadMember(
                        export,
                        "IntensityUnits"));

            var inverseSquared =
                Boolean(
                    ReadMember(
                        export,
                        "bUseInverseSquaredFalloff"));

            var falloffExponent =
                Number(
                    ReadMember(
                        export,
                        "LightFalloffExponent"));

            var sourceRadius =
                Number(
                    ReadMember(
                        export,
                        "SourceRadius"));

            var softSourceRadius =
                Number(
                    ReadMember(
                        export,
                        "SoftSourceRadius"));

            var sourceLength =
                Number(
                    ReadMember(
                        export,
                        "SourceLength"));

            var temperature =
                Number(
                    ReadMember(
                        export,
                        "Temperature"));

            var useTemperature =
                Boolean(
                    ReadMember(
                        export,
                        "bUseTemperature"));

            var castShadows =
                Boolean(
                    ReadMember(
                        export,
                        "CastShadows"));

            var visible =
                Boolean(
                    ReadMember(
                        export,
                        "bVisible"));

            var atmosphereSun =
                Boolean(
                    ReadMember(
                        export,
                        "bUsedAsAtmosphereSunLight"));

            if (intensity is null)
                throw new InvalidOperationException(
                    $"light intensity missing: {export.GetPathName()}");

            if (
                kind != "sky" &&
                lightColor is null)
            {
                throw new InvalidOperationException(
                    $"light color missing: {export.GetPathName()}");
            }

            if (
                (kind == "point" ||
                 kind == "spot") &&
                (radius is null ||
                 units is null))
            {
                throw new InvalidOperationException(
                    $"local light radius/units incomplete: {export.GetPathName()}");
            }

            if (
                kind == "spot" &&
                (innerCone is null ||
                 outerCone is null))
            {
                throw new InvalidOperationException(
                    $"spot cone incomplete: {export.GetPathName()}");
            }

            var actorPath =
                export.GetPathName() ?? "";

            var lastDot =
                actorPath.LastIndexOf('.');

            var parentPath =
                lastDot > 0
                    ? actorPath[..lastDot]
                    : "";

            var parentName =
                parentPath.Length > 0
                    ? parentPath.Split('.').Last()
                    : "";

            counts[kind] =
                counts.TryGetValue(
                    kind,
                    out var count)
                    ? count + 1
                    : 1;

            rows.Add(new {
                id = $"light_{rows.Count:0000}",
                packagePath = logicalPackage,
                actorName = parentName,
                componentName = export.Name,
                componentType = kind,
                sourceType = fullType,
                sourcePath = actorPath,
                hierarchy,
                properties = new {
                    intensity,
                    lightColor,
                    attenuationRadiusCm = radius,
                    innerConeAngleDegrees = innerCone,
                    outerConeAngleDegrees = outerCone,
                    intensityUnits = units,
                    useInverseSquaredFalloff =
                        inverseSquared,
                    lightFalloffExponent =
                        falloffExponent,
                    sourceRadiusCm = sourceRadius,
                    softSourceRadiusCm =
                        softSourceRadius,
                    sourceLengthCm = sourceLength,
                    temperatureKelvin =
                        temperature,
                    useTemperature,
                    visible,
                    castShadows,
                    usedAsAtmosphereSunLight =
                        atmosphereSun
                }
            });
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

if (packageFailures.Count != 0)
{
    throw new InvalidDataException(
        "UE light extraction package failures: " +
        JsonSerializer.Serialize(
            packageFailures));
}

if (rows.Count == 0)
    throw new InvalidDataException(
        "no supported UE light components found");

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
    lightCount = rows.Count,
    typeCounts = counts,
    lights = rows
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
    "XZIEL_UE_LIGHT_EXTRACT_GREEN " +
    JsonSerializer.Serialize(new {
        output.mapPackageCount,
        output.packagesLoaded,
        output.lightCount,
        output.typeCounts
    }));

return 0;
