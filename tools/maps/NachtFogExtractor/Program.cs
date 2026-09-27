using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Versions;
using System.Globalization;
using System.Reflection;
using System.Text.Json;

if (args.Length != 2)
    return 2;

const BindingFlags Flags =
    BindingFlags.Instance |
    BindingFlags.Public |
    BindingFlags.NonPublic;

object? Read(object target, string name)
{
    var field = target.GetType().GetField(name, Flags);
    if (field is not null) {
        try { return field.GetValue(target); } catch { }
    }

    var property = target.GetType().GetProperty(name, Flags);
    if (property is not null &&
        property.GetIndexParameters().Length == 0 &&
        property.GetMethod is not null) {
        try { return property.GetValue(target); } catch { }
    }

    return null;
}

string Text(object? value)
{
    if (value is null)
        return "";
    try { return value.ToString() ?? ""; }
    catch { return ""; }
}

double ParseLeadingNumber(string text)
{
    var token =
        text.Trim()
            .Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .FirstOrDefault();

    if (token is null ||
        !double.TryParse(
            token,
            NumberStyles.Float,
            CultureInfo.InvariantCulture,
            out var value))
        throw new InvalidOperationException(
            $"Unable to parse numeric property tag: {text}");

    return value;
}

double ReadAxis(object vector, string axis)
{
    var value = Read(vector, axis);
    if (value is null)
        throw new InvalidOperationException(
            $"Missing FVector axis {axis}");
    return Convert.ToDouble(
        value,
        CultureInfo.InvariantCulture);
}

var provider = new DefaultFileProvider(
    args[0],
    SearchOption.AllDirectories,
    true,
    new VersionContainer(EGame.GAME_UE4_21));
provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var maps = provider.Files.Values
    .Where(file =>
        Path.GetFileName(file.Path).Equals(
            "Nacht_de_Untoten.umap",
            StringComparison.OrdinalIgnoreCase))
    .Select(file => file.Path)
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .ToArray();

if (maps.Length != 1)
    return 3;

var exports =
    provider.LoadPackage(maps[0])
        .GetExports()
        .ToArray();

var fogs = exports
    .Where(export =>
        (export.GetType().FullName ??
         export.GetType().Name)
            .Contains(
                "ExponentialHeightFogComponent",
                StringComparison.OrdinalIgnoreCase))
    .ToArray();

if (fogs.Length != 1)
    return 4;

var fog = fogs[0];
var properties = Read(fog, "Properties");
var overrides =
    new SortedDictionary<string,double>(
        StringComparer.OrdinalIgnoreCase);

if (properties is System.Collections.IEnumerable enumerable)
{
    foreach (var tag in enumerable)
    {
        if (tag is null)
            continue;

        var name = Text(Read(tag, "Name"));
        var tagValue = Text(Read(tag, "Tag"));

        if (name is
            "FogDensity" or
            "FogHeightFalloff" or
            "FogMaxOpacity" or
            "StartDistance" or
            "FogCutoffDistance" or
            "VolumetricFogDistance")
        {
            overrides[name] =
                ParseLeadingNumber(tagValue);
        }
    }
}

if (!overrides.TryGetValue(
        "FogDensity",
        out var fogDensity) ||
    !overrides.TryGetValue(
        "FogHeightFalloff",
        out var heightFalloff) ||
    !overrides.TryGetValue(
        "FogMaxOpacity",
        out var maxOpacity) ||
    !overrides.TryGetValue(
        "StartDistance",
        out var startDistanceCm))
    return 5;

var relativeLocation =
    Read(fog, "RelativeLocation");

if (relativeLocation is null)
    return 6;

var locationUEcm = new {
    X = ReadAxis(relativeLocation, "X"),
    Y = ReadAxis(relativeLocation, "Y"),
    Z = ReadAxis(relativeLocation, "Z")
};

/*
 * UE4.21 UExponentialHeightFogComponent constructor defaults.
 * Only serialized property tags above override these values.
 */
const double DefaultFogColorR = 0.447;
const double DefaultFogColorG = 0.638;
const double DefaultFogColorB = 1.0;
const double DefaultSecondFogDensity = 0.0;
const double DefaultSecondFogHeightFalloff = 0.2;
const double DefaultSecondFogHeightOffsetCm = 0.0;
const double DefaultFogCutoffDistanceCm = 0.0;
const double DefaultDirectionalExponent = 4.0;
const double DefaultDirectionalStartDistanceCm = 10000.0;
const double DefaultDirectionalColorR = 0.25;
const double DefaultDirectionalColorG = 0.25;
const double DefaultDirectionalColorB = 0.125;
const bool DefaultVolumetricEnabled = false;
const double DefaultVolumetricDistanceCm = 6000.0;

var cutoffCm =
    overrides.TryGetValue(
        "FogCutoffDistance",
        out var serializedCutoff)
        ? serializedCutoff
        : DefaultFogCutoffDistanceCm;

var volumetricDistanceCm =
    overrides.TryGetValue(
        "VolumetricFogDistance",
        out var serializedVolumetricDistance)
        ? serializedVolumetricDistance
        : DefaultVolumetricDistanceCm;

var report = new {
    schemaVersion = 1,
    sourcePackage = maps[0],
    componentPath = fog.GetPathName() ?? "",
    defaultsSource =
        "UE4.21 UExponentialHeightFogComponent constructor",
    serializedOverrides = overrides,
    resolved = new {
        fogHeightMeters =
            locationUEcm.Z / 100.0,
        fogDensity,
        fogHeightFalloff = heightFalloff,
        fogColorLinear = new {
            r = DefaultFogColorR,
            g = DefaultFogColorG,
            b = DefaultFogColorB
        },
        fogMaxOpacity = maxOpacity,
        startDistanceMeters =
            startDistanceCm / 100.0,
        fogCutoffDistanceMeters =
            cutoffCm / 100.0,
        secondFogDensity =
            DefaultSecondFogDensity,
        secondFogHeightFalloff =
            DefaultSecondFogHeightFalloff,
        secondFogHeightMeters =
            (locationUEcm.Z +
             DefaultSecondFogHeightOffsetCm) / 100.0,
        directionalInscatteringExponent =
            DefaultDirectionalExponent,
        directionalInscatteringStartDistanceMeters =
            DefaultDirectionalStartDistanceCm / 100.0,
        directionalInscatteringColorLinear = new {
            r = DefaultDirectionalColorR,
            g = DefaultDirectionalColorG,
            b = DefaultDirectionalColorB
        },
        volumetricFogEnabled =
            DefaultVolumetricEnabled,
        volumetricFogDistanceMeters =
            volumetricDistanceCm / 100.0,
        inscatteringColorCubemap = (string?)null
    },
    sourceLocationUEcm = locationUEcm
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(args[1]))!);

File.WriteAllText(
    args[1],
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_NACHT_HEIGHT_FOG_RESOLVED " +
    JsonSerializer.Serialize(
        new {
            report.resolved.fogHeightMeters,
            report.resolved.fogDensity,
            report.resolved.fogHeightFalloff,
            report.resolved.fogMaxOpacity,
            report.resolved.startDistanceMeters,
            report.resolved.volumetricFogEnabled,
            report.resolved.volumetricFogDistanceMeters
        }));

return 0;
