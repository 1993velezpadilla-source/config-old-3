using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;

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
const uint NoMaterial = 0xffffffffu;
const uint VertexStride = 72u;
const uint SubmeshStride = 16u;

if (args.Length < 5 || args.Length > 7)
{
    Console.Error.WriteLine(
        "usage: UEStaticMeshXzmsProbe <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> <report-json> [mesh-count] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = Path.GetFullPath(args[3]);
var reportPath = Path.GetFullPath(args[4]);

var requestedMeshCount =
    args.Length >= 6 && int.TryParse(args[5], out var parsedCount)
        ? parsedCount
        : 8;

if (requestedMeshCount <= 0 || requestedMeshCount > 64)
    throw new ArgumentOutOfRangeException(
        nameof(requestedMeshCount),
        "mesh-count must be 1..64");

var sourceGameName = args.Length >= 7 ? args[6] : "ue5.1";

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" => EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" => EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " + sourceGameName)
    };

using var censusDoc =
    JsonDocument.Parse(File.ReadAllText(censusPath));

var candidatePackages =
    censusDoc.RootElement
        .GetProperty("packages")
        .EnumerateArray()
        .Where(row =>
        {
            var classes = row.GetProperty("classes");
            return classes.TryGetProperty(
                       "StaticMesh",
                       out var count) &&
                   count.GetInt32() > 0;
        })
        .Select(row => NormalizeMergedShardPath(
            row.GetProperty("packagePath").GetString()
            ?? throw new InvalidDataException("packagePath missing")))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
        .ToArray();

if (candidatePackages.Length < requestedMeshCount)
{
    throw new InvalidDataException(
        $"not enough StaticMesh packages: {candidatePackages.Length}");
}

var selectedPackages =
    EvenlySelect(candidatePackages, requestedMeshCount);

var provider =
    new DefaultFileProvider(
        root,
        SearchOption.AllDirectories,
        true,
        new VersionContainer(sourceGame))
    {
        MappingsContainer =
            new FileUsmapTypeMappingsProvider(mappingsPath)
    };

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var providerIndex = BuildProviderIndex(provider);

Directory.CreateDirectory(outputDir);
Directory.CreateDirectory(
    Path.GetDirectoryName(reportPath)!);

var converted = new List<object>();
var failures = new List<object>();

var totalVertices = 0L;
var totalIndices = 0L;
var totalSubmeshes = 0L;
var totalBytes = 0L;

for (var selectedIndex = 0;
     selectedIndex < selectedPackages.Length;
     ++selectedIndex)
{
    var logicalPath = selectedPackages[selectedIndex];
    var resolvedPath = ResolveProviderPackagePath(
        provider,
        providerIndex,
        logicalPath);

    if (resolvedPath is null)
    {
        failures.Add(new
        {
            packagePath = logicalPath,
            error = "provider path unresolved"
        });
        continue;
    }

    try
    {
        var package = provider.LoadPackage(resolvedPath);
        UStaticMesh? mesh = null;
        var exportIndex = -1;

        for (var i = 0;
             i < package.ExportMapLength;
             ++i)
        {
            var candidate = package.GetExport(i);
            if (candidate is UStaticMesh staticMesh)
            {
                mesh = staticMesh;
                exportIndex = i;
                break;
            }
        }

        if (mesh is null)
            throw new InvalidDataException(
                "package census promised StaticMesh but no UStaticMesh export was found");

        using var dto =
            new StaticMeshDto(
                mesh,
                EMeshQuality.Highest,
                ENaniteMeshFormat.NoNanite);

        if (dto.LODs.Count == 0)
            throw new InvalidDataException(
                "StaticMeshDto produced no LOD");

        var lod = dto.LODs[0];

        if (lod.Vertices.Length == 0 ||
            lod.Indices.Length == 0 ||
            lod.Indices.Length % 3 != 0)
        {
            throw new InvalidDataException(
                "highest LOD contains no valid triangles");
        }

        var key =
            Fnv1a64(
                logicalPath.ToLowerInvariant() +
                "#" +
                exportIndex.ToString(
                    System.Globalization.CultureInfo.InvariantCulture));

        var fileName =
            $"mesh-{selectedIndex:D2}-{key:x16}.xzm";
        var outputPath =
            Path.Combine(outputDir, fileName);

        var metrics =
            WriteXzms(outputPath, lod);

        var bytes = new FileInfo(outputPath).Length;
        var sha256 =
            Convert.ToHexString(
                SHA256.HashData(
                    File.ReadAllBytes(outputPath)))
                .ToLowerInvariant();

        totalVertices += metrics.VertexCount;
        totalIndices += metrics.IndexCount;
        totalSubmeshes += metrics.SubmeshCount;
        totalBytes += bytes;

        converted.Add(new
        {
            packagePath = logicalPath,
            resolvedPath,
            exportIndex,
            objectName = mesh.Name,
            sourceLodIndex = lod.SourceLodIndex,
            isNanite = lod.IsNanite,
            fileName,
            sha256,
            bytes,
            metrics.VertexCount,
            metrics.IndexCount,
            triangleCount = metrics.IndexCount / 3,
            metrics.SubmeshCount,
            metrics.UvSetCount,
            metrics.BoundsMin,
            metrics.BoundsMax
        });
    }
    catch (Exception e)
    {
        failures.Add(new
        {
            packagePath = logicalPath,
            resolvedPath,
            error = e.GetType().FullName + ": " + e.Message
        });
    }
}

var report = new
{
    schemaVersion = 1,
    sourceGameName,
    requestedMeshCount,
    candidatePackageCount = candidatePackages.Length,
    convertedMeshCount = converted.Count,
    failureCount = failures.Count,
    totalVertices,
    totalIndices,
    totalTriangles = totalIndices / 3,
    totalSubmeshes,
    totalBytes,
    converted,
    failures,
    ready =
        failures.Count == 0 &&
        converted.Count == requestedMeshCount &&
        totalVertices > 0 &&
        totalIndices > 0 &&
        totalSubmeshes > 0
};

File.WriteAllText(
    reportPath,
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions { WriteIndented = true }));

Console.WriteLine(
    "XZIEL_UE_STATIC_MESH_XZMS_PROBE " +
    JsonSerializer.Serialize(new
    {
        requestedMeshCount,
        candidatePackages = candidatePackages.Length,
        converted = converted.Count,
        failures = failures.Count,
        totalVertices,
        totalIndices,
        totalTriangles = totalIndices / 3,
        totalSubmeshes,
        totalBytes,
        report.ready
    }));

foreach (var failure in failures)
{
    Console.WriteLine(
        "XZIEL_UE_STATIC_MESH_XZMS_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!report.ready)
{
    Console.WriteLine(
        "XZIEL_UE_STATIC_MESH_XZMS_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_STATIC_MESH_XZMS_PROBE_GREEN");
return 0;

static XzmsMetrics WriteXzms(
    string path,
    MeshLodDto<MeshVertex> lod)
{
    var vertices = lod.Vertices;
    var indices = (uint[])lod.Indices.Clone();

    for (var i = 0; i < indices.Length; i += 3)
    {
        if (indices[i] >= vertices.Length ||
            indices[i + 1] >= vertices.Length ||
            indices[i + 2] >= vertices.Length)
        {
            throw new InvalidDataException(
                "index references vertex outside LOD vertex array");
        }

        /*
         * Unreal -> XZIEL reflects Y. Swap triangle winding so front-face
         * orientation remains unchanged after the handedness flip.
         */
        (indices[i + 1], indices[i + 2]) =
            (indices[i + 2], indices[i + 1]);
    }

    var min = new[]
    {
        float.PositiveInfinity,
        float.PositiveInfinity,
        float.PositiveInfinity
    };
    var max = new[]
    {
        float.NegativeInfinity,
        float.NegativeInfinity,
        float.NegativeInfinity
    };

    foreach (var vertex in vertices)
    {
        var p = ToXzielPosition(vertex.Position);
        for (var axis = 0; axis < 3; ++axis)
        {
            min[axis] = MathF.Min(min[axis], p[axis]);
            max[axis] = MathF.Max(max[axis], p[axis]);
        }
    }

    var uvSetCount =
        1 + Math.Min(3, lod.ExtraUvs.Length);

    var sections =
        lod.Sections
            .Where(s => s.NumFaces > 0)
            .ToArray();

    if (sections.Length == 0)
    {
        sections =
        [
            new MeshSectionDto(
                -1,
                0,
                indices.Length / 3,
                true)
        ];
    }

    foreach (var section in sections)
    {
        var first = section.FirstIndex;
        var count = checked(section.NumFaces * 3);

        if (first < 0 ||
            count <= 0 ||
            first > indices.Length ||
            count > indices.Length - first)
        {
            throw new InvalidDataException(
                "section index range is outside LOD index buffer");
        }
    }

    Directory.CreateDirectory(
        Path.GetDirectoryName(
            Path.GetFullPath(path))!);

    using var stream =
        new FileStream(
            path,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None);

    using var writer =
        new BinaryWriter(
            stream,
            Encoding.UTF8,
            leaveOpen: false);

    writer.Write(new byte[] { (byte)'X', (byte)'Z', (byte)'M', (byte)'S' });
    writer.Write(XzmsVersion);
    writer.Write((uint)vertices.Length);
    writer.Write((uint)indices.Length);
    writer.Write((uint)sections.Length);
    writer.Write(
        XzmsFlagXzielBasis |
        XzmsFlagIndexU32);
    writer.Write(VertexStride);
    writer.Write(SubmeshStride);

    for (var i = 0; i < 3; ++i)
        writer.Write(min[i]);
    for (var i = 0; i < 3; ++i)
        writer.Write(max[i]);

    for (var i = 0; i < vertices.Length; ++i)
    {
        var vertex = vertices[i];
        var p = ToXzielPosition(vertex.Position);
        var n = ToXzielDirection(
            vertex.Normal.X,
            vertex.Normal.Y,
            vertex.Normal.Z);
        var t = ToXzielDirection(
            vertex.Tangent.X,
            vertex.Tangent.Y,
            vertex.Tangent.Z);

        writer.Write(p[0]);
        writer.Write(p[1]);
        writer.Write(p[2]);

        writer.Write(n[0]);
        writer.Write(n[1]);
        writer.Write(n[2]);

        writer.Write(t[0]);
        writer.Write(t[1]);
        writer.Write(t[2]);

        /*
         * Reflection across Y reverses tangent-space handedness.
         */
        writer.Write(-(float)vertex.Tangent.W);

        writer.Write(vertex.Uv.U);
        writer.Write(vertex.Uv.V);

        for (var uv = 0; uv < 3; ++uv)
        {
            if (uv < lod.ExtraUvs.Length)
            {
                writer.Write(lod.ExtraUvs[uv][i].U);
                writer.Write(lod.ExtraUvs[uv][i].V);
            }
            else
            {
                writer.Write(0.0f);
                writer.Write(0.0f);
            }
        }
    }

    foreach (var index in indices)
        writer.Write(index);

    var attributeFlags =
        AttrPosition |
        AttrNormal |
        AttrUv0 |
        AttrTangent;

    if (lod.ExtraUvs.Length >= 1)
        attributeFlags |= AttrUv1;
    if (lod.ExtraUvs.Length >= 2)
        attributeFlags |= AttrUv2;
    if (lod.ExtraUvs.Length >= 3)
        attributeFlags |= AttrUv3;

    foreach (var section in sections)
    {
        writer.Write((uint)section.FirstIndex);
        writer.Write((uint)(section.NumFaces * 3));
        writer.Write(
            section.MaterialIndex >= 0
                ? (uint)section.MaterialIndex
                : NoMaterial);
        writer.Write(attributeFlags);
    }

    return new XzmsMetrics(
        vertices.Length,
        indices.Length,
        sections.Length,
        uvSetCount,
        min,
        max);
}

static float[] ToXzielPosition(
    CUE4Parse.UE4.Objects.Core.Math.FVector value)
{
    const float centimetersToMeters = 0.01f;

    return
    [
        (float)value.X * centimetersToMeters,
        -(float)value.Y * centimetersToMeters,
        (float)value.Z * centimetersToMeters
    ];
}

static float[] ToXzielDirection(
    double x,
    double y,
    double z)
{
    return
    [
        (float)x,
        -(float)y,
        (float)z
    ];
}

static string[] EvenlySelect(
    string[] values,
    int count)
{
    if (count == 1)
        return [values[0]];

    var selected = new List<string>(count);
    var seen =
        new HashSet<string>(
            StringComparer.OrdinalIgnoreCase);

    for (var i = 0; i < count; ++i)
    {
        var index =
            (int)Math.Round(
                (double)i *
                (values.Length - 1) /
                (count - 1));

        if (seen.Add(values[index]))
            selected.Add(values[index]);
    }

    for (var i = 0;
         selected.Count < count && i < values.Length;
         ++i)
    {
        if (seen.Add(values[i]))
            selected.Add(values[i]);
    }

    return selected.ToArray();
}

static ulong Fnv1a64(string value)
{
    const ulong offset = 14695981039346656037UL;
    const ulong prime = 1099511628211UL;

    var hash = offset;
    foreach (var b in Encoding.UTF8.GetBytes(value))
    {
        hash ^= b;
        hash *= prime;
    }

    return hash;
}

static Dictionary<string, string> BuildProviderIndex(
    DefaultFileProvider provider)
{
    var index =
        new Dictionary<string, string>(
            StringComparer.OrdinalIgnoreCase);

    foreach (var key in provider.Files.Keys)
    {
        var normalized = key.Replace('\\', '/');
        index.TryAdd(normalized, key);

        var firstSlash = normalized.IndexOf('/');
        if (firstSlash >= 0 &&
            firstSlash + 1 < normalized.Length)
        {
            index.TryAdd(
                normalized[(firstSlash + 1)..],
                key);
        }

        foreach (var marker in new[]
                 {
                     "/Pavlov/",
                     "/Engine/"
                 })
        {
            var pos =
                normalized.IndexOf(
                    marker,
                    StringComparison.OrdinalIgnoreCase);

            if (pos >= 0)
            {
                index.TryAdd(
                    normalized[(pos + 1)..],
                    key);
            }
        }
    }

    return index;
}

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    IReadOnlyDictionary<string, string> providerIndex,
    string logicalPath)
{
    if (provider.TryGetGameFile(logicalPath, out _))
        return logicalPath;

    var normalized =
        logicalPath.Replace('\\', '/');

    if (providerIndex.TryGetValue(
            normalized,
            out var exact))
        return exact;

    return provider.Files.Keys.FirstOrDefault(
        key => key.EndsWith(
            normalized,
            StringComparison.OrdinalIgnoreCase));
}

static string NormalizeMergedShardPath(
    string path)
{
    var normalized =
        path.Replace('\\', '/');

    if (!normalized.StartsWith(
            "shard-",
            StringComparison.OrdinalIgnoreCase))
        return normalized;

    var slash = normalized.IndexOf('/');
    if (slash <= 6)
        return normalized;

    var shardNumber =
        normalized.AsSpan(
            6,
            slash - 6);

    for (var i = 0;
         i < shardNumber.Length;
         ++i)
    {
        if (!char.IsDigit(
                shardNumber[i]))
            return normalized;
    }

    return normalized[(slash + 1)..];
}

sealed record XzmsMetrics(
    int VertexCount,
    int IndexCount,
    int SubmeshCount,
    int UvSetCount,
    float[] BoundsMin,
    float[] BoundsMax);
