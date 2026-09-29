using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;
using System.Text.Json;

if (args.Length != 7)
{
    Console.Error.WriteLine(
        "usage: UEStaticMeshAudit <root> <mappings.usmap> <class-census.json> <output.json> <shard-index> <shard-count> <source-game>");
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
var allRows = censusDoc.RootElement.GetProperty("packages").EnumerateArray()
    .Select((row, index) => new {
        Index = index,
        Path = NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("missing packagePath")),
        StaticMeshCount =
            row.GetProperty("classes").TryGetProperty("StaticMesh", out var c)
                ? c.GetInt32()
                : 0
    })
    .Where(x => x.StaticMeshCount > 0)
    .ToArray();

var packageRows = allRows
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
var uvChannelCounts = new SortedDictionary<int, int>();

var expectedMeshes = packageRows.Sum(x => x.StaticMeshCount);
var packagesLoaded = 0;
var meshesDecoded = 0;
long vertices = 0;
long indices = 0;
long triangles = 0;
long sections = 0;
long materials = 0;
var maxUvChannels = 0;
var maxVertices = 0;
var maxTriangles = 0;
string? maxUvObject = null;
string? maxVertexObject = null;
string? maxTriangleObject = null;

foreach (var row in packageRows)
{
    var resolved = ResolveProviderPackagePath(provider, row.Path);
    if (resolved is null)
    {
        failures.Add(new {
            packagePath = row.Path,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolved);
        packagesLoaded++;

        var packageMeshes = package.GetExports().OfType<UStaticMesh>().ToArray();
        if (packageMeshes.Length != row.StaticMeshCount)
        {
            failures.Add(new {
                packagePath = row.Path,
                error = $"static mesh count mismatch census={row.StaticMeshCount} decoded={packageMeshes.Length}"
            });
            continue;
        }

        foreach (var mesh in packageMeshes)
        {
            try
            {
                using var dto = new StaticMeshDto(
                    mesh,
                    EMeshQuality.Highest,
                    ENaniteMeshFormat.NoNanite);

                if (dto.LODs.Count != 1)
                    throw new InvalidDataException(
                        $"expected exactly one highest-quality LOD, got {dto.LODs.Count}");

                var lod = dto.LODs[0];
                if (lod.Vertices.Length <= 0 ||
                    lod.Indices.Length <= 0 ||
                    lod.Indices.Length % 3 != 0)
                {
                    throw new InvalidDataException(
                        $"invalid mesh geometry vertices={lod.Vertices.Length} indices={lod.Indices.Length}");
                }

                var uvChannels = 1 + lod.ExtraUvs.Length;
                if (uvChannels > 8)
                    throw new InvalidDataException(
                        $"source uses {uvChannels} UV channels; XZMS v4 maximum is 8");

                meshesDecoded++;
                vertices += lod.Vertices.Length;
                indices += lod.Indices.Length;
                triangles += lod.Indices.Length / 3;
                sections += lod.Sections.Count(s => s.IsValid && s.NumFaces > 0);
                materials += dto.Materials.Length;

                uvChannelCounts[uvChannels] =
                    uvChannelCounts.GetValueOrDefault(uvChannels) + 1;

                if (uvChannels > maxUvChannels)
                {
                    maxUvChannels = uvChannels;
                    maxUvObject = mesh.GetPathName();
                }

                if (lod.Vertices.Length > maxVertices)
                {
                    maxVertices = lod.Vertices.Length;
                    maxVertexObject = mesh.GetPathName();
                }

                var meshTriangles = lod.Indices.Length / 3;
                if (meshTriangles > maxTriangles)
                {
                    maxTriangles = meshTriangles;
                    maxTriangleObject = mesh.GetPathName();
                }
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = row.Path,
                    objectPath = mesh.GetPathName(),
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = row.Path,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ready =
    failures.Count == 0 &&
    packagesLoaded == packageRows.Length &&
    meshesDecoded == expectedMeshes &&
    meshesDecoded > 0 &&
    maxUvChannels is >= 1 and <= 8;

var report = new {
    schemaVersion = 1,
    sourceGameName,
    shardIndex,
    shardCount,
    packageCount = packageRows.Length,
    packagesLoaded,
    expectedMeshes,
    meshesDecoded,
    failureCount = failures.Count,
    vertices,
    indices,
    triangles,
    sections,
    materials,
    maxUvChannels,
    uvChannelCounts,
    maxUvObject,
    maxVertices,
    maxVertexObject,
    maxTriangles,
    maxTriangleObject,
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
    "XZIEL_UE_STATIC_MESH_AUDIT " +
    JsonSerializer.Serialize(new {
        shardIndex,
        shardCount,
        packages = packageRows.Length,
        packagesLoaded,
        expectedMeshes,
        meshesDecoded,
        failures = failures.Count,
        vertices,
        triangles,
        sections,
        maxUvChannels,
        ready
    }));

if (!ready)
{
    foreach (var failure in failures.Take(100))
        Console.WriteLine(
            "XZIEL_UE_STATIC_MESH_AUDIT_FAILURE " +
            JsonSerializer.Serialize(failure));
    return 5;
}

return 0;

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
