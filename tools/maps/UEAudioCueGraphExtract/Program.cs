using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Assets.Exports.Sound.Node;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using System.Text.Json;
using System.Text.RegularExpressions;

if (args.Length != 5)
{
    Console.Error.WriteLine(
        "usage: UEAudioCueGraphExtract <unpacked-root> <mappings.usmap> <class-census.json> <output.json> <source-game>");
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
            return file.Path;
    }
    return null;
}

string? RefPath(FPackageIndex? index)
{
    if (index is null || index.IsNull)
        return null;
    return index.ResolvedObject?.GetPathName()
        ?? index.Name;
}

using var censusDoc =
    JsonDocument.Parse(File.ReadAllText(censusPath));

var candidatePackages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Where(row =>
    {
        if (!row.TryGetProperty("classes", out var classes))
            return false;
        return classes.TryGetProperty("SoundCue", out var count)
            && count.GetInt32() > 0;
    })
    .Select(row =>
        NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
    .ToArray();

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

var cueRows = new List<object>();
var failures = new List<object>();
var unresolvedNodeRefs = new List<object>();
var packagesLoaded = 0;
var totalNodes = 0;
var totalEdges = 0;
var totalWaveRefs = 0;
var nodeTypeCounts =
    new SortedDictionary<string, int>(StringComparer.Ordinal);

foreach (var logicalPackage in candidatePackages)
{
    var resolved =
        ResolveProviderPackagePath(provider, logicalPackage);
    if (resolved is null)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        foreach (var cue in package.GetExports()
                     .OfType<USoundCue>()
                     .OrderBy(x => x.GetPathName(), StringComparer.Ordinal))
        {
            var nodes = new List<object>();
            var edges = new List<object>();
            var waveRefs = new SortedSet<string>(
                StringComparer.OrdinalIgnoreCase);
            var visited = new HashSet<string>(
                StringComparer.Ordinal);
            var queue = new Queue<FPackageIndex>();

            if (cue.FirstNode is { } first && !first.IsNull)
                queue.Enqueue(first);

            while (queue.Count > 0)
            {
                var index = queue.Dequeue();
                var referencePath =
                    index.ResolvedObject?.GetPathName()
                    ?? index.Name;

                USoundNode? node = null;
                try
                {
                    node = index.Load<USoundNode>();
                }
                catch (Exception ex)
                {
                    unresolvedNodeRefs.Add(new {
                        cuePath = cue.GetPathName(),
                        reference = referencePath,
                        error = ex.GetType().Name + ": " + ex.Message
                    });
                }

                if (node is null)
                {
                    unresolvedNodeRefs.Add(new {
                        cuePath = cue.GetPathName(),
                        reference = referencePath,
                        error = "node load returned null"
                    });
                    continue;
                }

                var nodePath = node.GetPathName();
                if (!visited.Add(nodePath))
                    continue;

                var nodeType = node.ExportType;
                nodeTypeCounts[nodeType] =
                    nodeTypeCounts.GetValueOrDefault(nodeType) + 1;

                string? wavePath = null;
                if (node is USoundNodeWavePlayer wavePlayer &&
                    wavePlayer.SoundWave is { } waveIndex &&
                    !waveIndex.IsNull)
                {
                    wavePath =
                        waveIndex.ResolvedObject?.GetPathName()
                        ?? waveIndex.Name;
                    if (!string.IsNullOrWhiteSpace(wavePath))
                    {
                        waveRefs.Add(wavePath);
                        totalWaveRefs++;
                    }
                }

                var childPaths = new List<string>();
                foreach (var child in node.ChildNodes ?? Array.Empty<FPackageIndex>())
                {
                    if (child.IsNull)
                        continue;
                    var childPath =
                        child.ResolvedObject?.GetPathName()
                        ?? child.Name;
                    childPaths.Add(childPath);
                    edges.Add(new {
                        from = nodePath,
                        to = childPath
                    });
                    totalEdges++;
                    queue.Enqueue(child);
                }

                nodes.Add(new {
                    objectPath = nodePath,
                    exportType = nodeType,
                    wavePath,
                    children = childPaths
                });
                totalNodes++;
            }

            cueRows.Add(new {
                packagePath = logicalPackage,
                objectPath = cue.GetPathName(),
                exportType = cue.ExportType,
                volumeMultiplier = cue.VolumeMultiplier,
                pitchMultiplier = cue.PitchMultiplier,
                firstNode = RefPath(cue.FirstNode),
                nodeCount = nodes.Count,
                edgeCount = edges.Count,
                waveReferenceCount = waveRefs.Count,
                waveObjectPaths = waveRefs.ToArray(),
                nodes,
                edges
            });
        }
    }
    catch (Exception ex)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = ex.GetType().Name + ": " + ex.Message
        });
    }
}

var ready =
    candidatePackages.Length > 0 &&
    packagesLoaded == candidatePackages.Length &&
    failures.Count == 0 &&
    cueRows.Count > 0;

var output = new {
    schemaVersion = 1,
    sourceGame = sourceGameName,
    candidatePackageCount = candidatePackages.Length,
    packagesLoaded,
    cueCount = cueRows.Count,
    totalNodes,
    totalEdges,
    totalWaveRefs,
    unresolvedNodeReferenceCount = unresolvedNodeRefs.Count,
    nodeTypeCounts,
    cues = cueRows,
    unresolvedNodeReferences = unresolvedNodeRefs,
    failures,
    ready
};

Directory.CreateDirectory(
    Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
File.WriteAllText(
    outputPath,
    JsonSerializer.Serialize(
        output,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_AUDIO_CUE_GRAPH " +
    JsonSerializer.Serialize(new {
        output.candidatePackageCount,
        output.packagesLoaded,
        output.cueCount,
        output.totalNodes,
        output.totalEdges,
        output.totalWaveRefs,
        output.unresolvedNodeReferenceCount,
        failureCount = failures.Count,
        output.ready
    }));

if (!ready)
{
    Console.WriteLine("XZIEL_UE_AUDIO_CUE_GRAPH_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_AUDIO_CUE_GRAPH_GREEN");
return 0;
