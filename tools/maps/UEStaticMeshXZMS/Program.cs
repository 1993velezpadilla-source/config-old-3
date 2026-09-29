using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;
using System.Text.Json;

const uint XzmsVersion = 3;
const uint XzmsFlagXzielBasis = 1u << 0;
const uint XzmsFlagIndexU32 = 1u << 1;
const uint AttrPosition = 1u << 0;
const uint AttrNormal = 1u << 1;
const uint AttrUv0 = 1u << 2;
const uint AttrUv1 = 1u << 3;
const uint AttrUv2 = 1u << 4;
const uint AttrUv3 = 1u << 5;
const uint AttrTangent = 1u << 6;
const uint VertexStride = 72;
const uint SubmeshStride = 16;
const float UnrealCentimetersToMeters = 0.01f;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UEStaticMeshXZMS <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-meshes] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxMeshes = args.Length >= 5 ? int.Parse(args[4]) : 8;
var sourceGameName = args.Length >= 6 ? args[5] : "ue5.1";

if (maxMeshes <= 0)
    throw new ArgumentOutOfRangeException(nameof(maxMeshes));

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

using var censusDoc = JsonDocument.Parse(File.ReadAllText(censusPath));
var candidatePackages = censusDoc.RootElement
    .GetProperty("packages")
    .EnumerateArray()
    .Where(row =>
        row.GetProperty("classes")
            .TryGetProperty("StaticMesh", out var count) &&
        count.GetInt32() > 0)
    .Select(row =>
        NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
    .ToArray();

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

Directory.CreateDirectory(outputDir);

var rows = new List<object>();
var failures = new List<object>();
var converted = 0;
long totalVertices = 0;
long totalIndices = 0;
long totalTriangles = 0;
long totalBytes = 0;

foreach (var logicalPackage in candidatePackages)
{
    if (converted >= maxMeshes)
        break;

    var resolvedPath = ResolveProviderPackagePath(provider, logicalPackage);
    if (resolvedPath is null)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolvedPath);
        var meshes = package.GetExports()
            .OfType<UStaticMesh>()
            .OrderBy(mesh => mesh.Name, StringComparer.Ordinal)
            .ToArray();

        foreach (var mesh in meshes)
        {
            if (converted >= maxMeshes)
                break;

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
                var fileName = $"m{converted:D4}.xzm";
                var outPath = Path.Combine(outputDir, fileName);
                var result = WriteXzms(outPath, lod);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath = resolvedPath,
                    objectPath = mesh.GetPathName(),
                    sourceLodIndex = lod.SourceLodIndex,
                    sourceMaterialCount = dto.Materials.Length,
                    sourceSectionCount = lod.Sections.Length,
                    sourceUvChannelCount = 1 + lod.ExtraUvs.Length,
                    result.vertexCount,
                    result.indexCount,
                    result.triangleCount,
                    result.submeshCount,
                    result.bytes,
                    result.boundsMin,
                    result.boundsMax
                });

                converted++;
                totalVertices += result.vertexCount;
                totalIndices += result.indexCount;
                totalTriangles += result.triangleCount;
                totalBytes += result.bytes;
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    objectPath = mesh.GetPathName(),
                    error = e.GetType().FullName + ": " + e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var ready =
    converted == maxMeshes &&
    failures.Count == 0 &&
    rows.Count == maxMeshes &&
    totalVertices > 0 &&
    totalIndices > 0 &&
    totalTriangles > 0;

var report = new {
    schemaVersion = 1,
    format = "xziel_ue_static_mesh_xzms_probe_v1",
    sourceGameName,
    coordinateSystem = new {
        source = "Unreal X,Y,Z centimeters",
        runtime = "XZIEL X,-Y,Z meters",
        centimetersToMeters = UnrealCentimetersToMeters,
        mirrorAxis = "Y",
        mirroredTriangleWinding = true,
        tangentHandednessFlipped = true
    },
    requestedMeshes = maxMeshes,
    convertedMeshes = converted,
    failureCount = failures.Count,
    totalVertices,
    totalIndices,
    totalTriangles,
    totalBytes,
    meshes = rows,
    failures,
    ready
};

var reportPath = Path.Combine(outputDir, "report.json");
File.WriteAllText(
    reportPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_XZMS_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxMeshes,
        converted,
        failures = failures.Count,
        totalVertices,
        totalIndices,
        totalTriangles,
        totalBytes,
        ready
    }));

foreach (var failure in failures.Take(30))
{
    Console.WriteLine(
        "XZIEL_UE_XZMS_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine("XZIEL_UE_XZMS_PROBE_FAILURE");
    return 5;
}

Console.WriteLine("XZIEL_UE_XZMS_PROBE_GREEN");
return 0;

static (
    int vertexCount,
    int indexCount,
    int triangleCount,
    int submeshCount,
    long bytes,
    float[] boundsMin,
    float[] boundsMax
) WriteXzms(
    string outputPath,
    MeshLodDto<MeshVertex> lod)
{
    if (lod.Vertices.Length == 0)
        throw new InvalidDataException("LOD has no vertices");
    if (lod.Indices.Length == 0)
        throw new InvalidDataException("LOD has no indices");
    if (lod.ExtraUvs.Length > 3)
        throw new InvalidDataException(
            $"XZMS v3 supports 4 UV channels total; source has {1 + lod.ExtraUvs.Length}");

    var sections = lod.Sections
        .Where(section => section.IsValid && section.NumFaces > 0)
        .ToArray();

    if (sections.Length == 0)
        throw new InvalidDataException("LOD has no non-empty valid sections");

    var outputIndices = new List<uint>();
    var outputSubmeshes = new List<(uint first, uint count, uint material, uint attrs)>();

    uint attrs = AttrPosition | AttrNormal | AttrUv0 | AttrTangent;
    if (lod.ExtraUvs.Length >= 1) attrs |= AttrUv1;
    if (lod.ExtraUvs.Length >= 2) attrs |= AttrUv2;
    if (lod.ExtraUvs.Length >= 3) attrs |= AttrUv3;

    foreach (var section in sections)
    {
        var sourceFirst = checked(section.FirstIndex);
        var sourceCount = checked(section.NumFaces * 3);
        if (sourceFirst < 0 ||
            sourceCount <= 0 ||
            sourceFirst > lod.Indices.Length - sourceCount)
        {
            throw new InvalidDataException(
                $"section index range invalid first={sourceFirst} count={sourceCount} sourceIndices={lod.Indices.Length}");
        }

        var outputFirst = checked((uint)outputIndices.Count);

        for (var i = 0; i < sourceCount; i += 3)
        {
            var a = lod.Indices[sourceFirst + i + 0];
            var b = lod.Indices[sourceFirst + i + 1];
            var c = lod.Indices[sourceFirst + i + 2];

            if (a >= lod.Vertices.Length ||
                b >= lod.Vertices.Length ||
                c >= lod.Vertices.Length)
            {
                throw new InvalidDataException(
                    $"triangle references vertex outside range ({a},{b},{c})/{lod.Vertices.Length}");
            }

            // X,Y,Z -> X,-Y,Z is a reflection. Swap B/C so front-face
            // orientation remains identical after the basis conversion.
            outputIndices.Add(a);
            outputIndices.Add(c);
            outputIndices.Add(b);
        }

        outputSubmeshes.Add((
            outputFirst,
            checked((uint)sourceCount),
            checked((uint)section.MaterialIndex),
            attrs));
    }

    if (outputIndices.Count == 0 || outputIndices.Count % 3 != 0)
        throw new InvalidDataException("converted triangle index stream is invalid");

    var min = new[] { float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity };
    var max = new[] { float.NegativeInfinity, float.NegativeInfinity, float.NegativeInfinity };

    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
    using var stream = new FileStream(outputPath, FileMode.Create, FileAccess.Write, FileShare.None);
    using var writer = new BinaryWriter(stream);

    writer.Write((byte)'X');
    writer.Write((byte)'Z');
    writer.Write((byte)'M');
    writer.Write((byte)'S');
    writer.Write(XzmsVersion);
    writer.Write(checked((uint)lod.Vertices.Length));
    writer.Write(checked((uint)outputIndices.Count));
    writer.Write(checked((uint)outputSubmeshes.Count));
    writer.Write(XzmsFlagXzielBasis | XzmsFlagIndexU32);
    writer.Write(VertexStride);
    writer.Write(SubmeshStride);

    // Bounds are patched after writing vertices.
    var boundsOffset = stream.Position;
    for (var i = 0; i < 6; ++i) writer.Write(0.0f);

    for (var i = 0; i < lod.Vertices.Length; ++i)
    {
        var v = lod.Vertices[i];

        var px = checked((float)v.Position.X) * UnrealCentimetersToMeters;
        var py = -checked((float)v.Position.Y) * UnrealCentimetersToMeters;
        var pz = checked((float)v.Position.Z) * UnrealCentimetersToMeters;

        var nx = checked((float)v.Normal.X);
        var ny = -checked((float)v.Normal.Y);
        var nz = checked((float)v.Normal.Z);

        var tx = checked((float)v.Tangent.X);
        var ty = -checked((float)v.Tangent.Y);
        var tz = checked((float)v.Tangent.Z);
        var tw = -checked((float)v.Tangent.W);

        if (!float.IsFinite(px) || !float.IsFinite(py) || !float.IsFinite(pz) ||
            !float.IsFinite(nx) || !float.IsFinite(ny) || !float.IsFinite(nz) ||
            !float.IsFinite(tx) || !float.IsFinite(ty) || !float.IsFinite(tz) ||
            !float.IsFinite(tw))
        {
            throw new InvalidDataException($"non-finite vertex {i}");
        }

        min[0] = MathF.Min(min[0], px);
        min[1] = MathF.Min(min[1], py);
        min[2] = MathF.Min(min[2], pz);
        max[0] = MathF.Max(max[0], px);
        max[1] = MathF.Max(max[1], py);
        max[2] = MathF.Max(max[2], pz);

        writer.Write(px); writer.Write(py); writer.Write(pz);
        writer.Write(nx); writer.Write(ny); writer.Write(nz);
        writer.Write(tx); writer.Write(ty); writer.Write(tz); writer.Write(tw);

        writer.Write(v.Uv.U); writer.Write(v.Uv.V);

        for (var uvChannel = 0; uvChannel < 3; ++uvChannel)
        {
            if (uvChannel < lod.ExtraUvs.Length)
            {
                var uv = lod.ExtraUvs[uvChannel][i];
                writer.Write(uv.U);
                writer.Write(uv.V);
            }
            else
            {
                writer.Write(0.0f);
                writer.Write(0.0f);
            }
        }
    }

    foreach (var index in outputIndices)
        writer.Write(index);

    foreach (var submesh in outputSubmeshes)
    {
        writer.Write(submesh.first);
        writer.Write(submesh.count);
        writer.Write(submesh.material);
        writer.Write(submesh.attrs);
    }

    var end = stream.Position;
    stream.Position = boundsOffset;
    writer.Write(min[0]); writer.Write(min[1]); writer.Write(min[2]);
    writer.Write(max[0]); writer.Write(max[1]); writer.Write(max[2]);
    stream.Position = end;
    writer.Flush();

    return (
        lod.Vertices.Length,
        outputIndices.Count,
        outputIndices.Count / 3,
        outputSubmeshes.Count,
        stream.Length,
        min,
        max);
}

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
    {
        if (!char.IsDigit(shardNumber[i]))
            return normalized;
    }

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
        .Where(key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase))
        .OrderBy(key => key.Length)
        .ThenBy(key => key, StringComparer.OrdinalIgnoreCase)
        .FirstOrDefault();
}
