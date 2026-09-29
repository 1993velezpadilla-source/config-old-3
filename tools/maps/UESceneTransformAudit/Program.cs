using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

if (args.Length != 7)
{
    Console.Error.WriteLine(
        "usage: UESceneTransformAudit <root> <mappings.usmap> <class-census.json> <output.json> <shard-index> <shard-count> <source-game>");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputPath = args[3];
var shardIndex = int.Parse(args[4]);
var shardCount = int.Parse(args[5]);
var sourceGameName = args[6];

if (shardCount <= 0 || shardIndex < 0 || shardIndex >= shardCount)
    throw new ArgumentOutOfRangeException(nameof(shardIndex));

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        _ => throw new ArgumentException("unsupported source-game: " + sourceGameName)
    };

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var packageRows = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Select((row, index) => new {
        Index = index,
        Path = NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("missing packagePath"))
    })
    .Where(x => x.Index % shardCount == shardIndex)
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

var failures = new List<object>();
var typeCounts = new SortedDictionary<string, int>(StringComparer.Ordinal);

var packagesLoaded = 0;
var sceneComponents = 0;
var attachedComponents = 0;
var absoluteLocation = 0;
var absoluteRotation = 0;
var absoluteScale = 0;
var anyAbsolute = 0;
var negativeScale = 0;
var zeroScale = 0;
var nonFiniteTransform = 0;

foreach (var packageRow in packageRows)
{
    var resolved = ResolveProviderPackagePath(provider, packageRow.Path);
    if (resolved is null)
    {
        failures.Add(new {
            packagePath = packageRow.Path,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        for (var i = 0; i < package.ExportMapLength; ++i)
        {
            try
            {
                if (package.GetExport(i) is not USceneComponent component)
                    continue;

                sceneComponents++;
                typeCounts[component.ExportType] =
                    typeCounts.GetValueOrDefault(component.ExportType) + 1;

                if (component.AttachParent is not null)
                    attachedComponents++;

                var absLoc = component.GetOrDefault<bool>("bAbsoluteLocation");
                var absRot = component.GetOrDefault<bool>("bAbsoluteRotation");
                var absScale = component.GetOrDefault<bool>("bAbsoluteScale");

                if (absLoc) absoluteLocation++;
                if (absRot) absoluteRotation++;
                if (absScale) absoluteScale++;
                if (absLoc || absRot || absScale) anyAbsolute++;

                var transform = component.GetRelativeTransform();
                var s = transform.Scale3D;
                if (s.X < 0 || s.Y < 0 || s.Z < 0)
                    negativeScale++;
                if (Math.Abs((double)s.X) <= 1.0e-8 ||
                    Math.Abs((double)s.Y) <= 1.0e-8 ||
                    Math.Abs((double)s.Z) <= 1.0e-8)
                    zeroScale++;

                if (!Finite(transform.Translation.X) ||
                    !Finite(transform.Translation.Y) ||
                    !Finite(transform.Translation.Z) ||
                    !Finite(transform.Rotation.X) ||
                    !Finite(transform.Rotation.Y) ||
                    !Finite(transform.Rotation.Z) ||
                    !Finite(transform.Rotation.W) ||
                    !Finite(transform.Scale3D.X) ||
                    !Finite(transform.Scale3D.Y) ||
                    !Finite(transform.Scale3D.Z))
                {
                    nonFiniteTransform++;
                }
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = packageRow.Path,
                    exportIndex = i,
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = packageRow.Path,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ready =
    packagesLoaded == packageRows.Length &&
    failures.Count == 0 &&
    sceneComponents > 0 &&
    nonFiniteTransform == 0;

var report = new {
    schemaVersion = 1,
    sourceGameName,
    shardIndex,
    shardCount,
    packageCount = packageRows.Length,
    packagesLoaded,
    failureCount = failures.Count,
    sceneComponents,
    attachedComponents,
    absoluteLocation,
    absoluteRotation,
    absoluteScale,
    anyAbsolute,
    negativeScale,
    zeroScale,
    nonFiniteTransform,
    typeCounts,
    failures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_SCENE_TRANSFORM_AUDIT " +
    JsonSerializer.Serialize(new {
        shardIndex,
        shardCount,
        packages = packageRows.Length,
        packagesLoaded,
        failures = failures.Count,
        sceneComponents,
        attachedComponents,
        absoluteLocation,
        absoluteRotation,
        absoluteScale,
        anyAbsolute,
        negativeScale,
        zeroScale,
        nonFiniteTransform,
        ready
    }));

if (!ready)
{
    foreach (var failure in failures.Take(50))
        Console.WriteLine(
            "XZIEL_UE_SCENE_TRANSFORM_FAILURE " +
            JsonSerializer.Serialize(failure));
    return 5;
}

return 0;

static bool Finite<T>(T value) where T : struct, IConvertible
    => double.IsFinite(Convert.ToDouble(value));

static string NormalizeMergedShardPath(string path)
{
    var normalized = path.Replace('\\', '/');
    if (!normalized.StartsWith("shard-", StringComparison.OrdinalIgnoreCase))
        return normalized;

    var slash = normalized.IndexOf('/');
    if (slash <= 6)
        return normalized;

    var shardNumber = normalized.AsSpan(6, slash - 6);
    for (var i = 0; i < shardNumber.Length; ++i)
        if (!char.IsDigit(shardNumber[i]))
            return normalized;

    return normalized[(slash + 1)..];
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized = logicalPath.Replace('\\', '/').TrimStart('/');

    if (provider.Files.ContainsKey(normalized))
        return normalized;

    return provider.Files.Keys
        .Where(key => key.EndsWith(normalized, StringComparison.OrdinalIgnoreCase))
        .OrderBy(key => key.Length)
        .ThenBy(key => key, StringComparer.OrdinalIgnoreCase)
        .FirstOrDefault();
}
