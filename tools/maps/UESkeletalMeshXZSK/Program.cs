using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;
using System.Text;
using System.Text.Json;

const uint XzskVersion = 2;
const uint XzskHeaderBytes = 112;
const uint XzskBoneBytes = 56;
const uint XzskVertexBytes = 136;
const uint XzskSectionBytes = 16;
const uint XzskMaxUvs = 8;
const uint XzskMaxInfluences = 8;
const uint FlagXzielBasis = 1u << 0;
const uint FlagIndexU32 = 1u << 1;
const uint FlagSkeletonRemap = 1u << 2;

if (args.Length is < 4 or > 6)
{
    Console.Error.WriteLine(
        "usage: UESkeletalMeshXZSK <unpacked-root> <mappings.usmap> <class-census.json> <output-dir> [max-meshes] [source-game]");
    return 2;
}

var root = args[0];
var mappingsPath = args[1];
var censusPath = args[2];
var outputDir = args[3];
var maxMeshes =
    args.Length >= 5
        ? int.Parse(args[4])
        : 8;
var sourceGameName =
    args.Length >= 6
        ? args[5]
        : "ue5.1";

if (maxMeshes <= 0)
    throw new ArgumentOutOfRangeException(nameof(maxMeshes));

EGame sourceGame =
    sourceGameName.Trim().ToLowerInvariant() switch
    {
        "ue4.21" or "ue4_21" or "ue421" =>
            EGame.GAME_UE4_21,
        "ue5.1" or "ue5_1" or "ue51" =>
            EGame.GAME_UE5_1,
        _ => throw new ArgumentException(
            "unsupported source-game: " +
            sourceGameName)
    };

using var censusDoc =
    JsonDocument.Parse(
        File.ReadAllText(censusPath));

var candidatePackages =
    censusDoc.RootElement
        .GetProperty("packages")
        .EnumerateArray()
        .Where(row =>
            row.GetProperty("classes")
                .TryGetProperty(
                    "SkeletalMesh",
                    out var count) &&
            count.GetInt32() > 0)
        .Select(row =>
            NormalizeMergedShardPath(
                row.GetProperty("packagePath")
                    .GetString()
                ?? throw new InvalidDataException(
                    "packagePath missing")))
        .Distinct(
            StringComparer.OrdinalIgnoreCase)
        .OrderBy(
            x => x,
            StringComparer.OrdinalIgnoreCase)
        .ToArray();

var provider = new DefaultFileProvider(
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

Directory.CreateDirectory(outputDir);

var rows = new List<object>();
var failures = new List<object>();
var hashes = new SortedDictionary<string, int>(
    StringComparer.Ordinal);
var meshLayoutHashes = new SortedDictionary<string, int>(
    StringComparer.Ordinal);

var converted = 0;
long totalBones = 0;
long totalVertices = 0;
long totalIndices = 0;
long totalTriangles = 0;
long totalSections = 0;
long totalFileBytes = 0;
var maxUvChannels = 0;
var maxInfluences = 0;
var selfRigFallbackCount = 0;

foreach (var logicalPackage in candidatePackages)
{
    if (converted >= maxMeshes)
        break;

    var resolvedPath =
        ResolveProviderPackagePath(
            provider,
            logicalPackage);

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
        var package =
            provider.LoadPackage(
                resolvedPath);

        var meshes =
            package.GetExports()
                .OfType<USkeletalMesh>()
                .OrderBy(
                    mesh => mesh.Name,
                    StringComparer.Ordinal)
                .ToArray();

        foreach (var mesh in meshes)
        {
            if (converted >= maxMeshes)
                break;

            try
            {
                USkeleton? animationSkeleton = null;
                string skeletonPackagePath;
                string skeletonPath;
                var selfRig =
                    mesh.Skeleton.IsNull;

                if (selfRig)
                {
                    skeletonPackagePath =
                        resolvedPath;
                    skeletonPath =
                        mesh.GetPathName() +
                        "#ReferenceSkeleton";
                }
                else
                {
                    animationSkeleton =
                        ResolveMeshSkeleton(
                            provider,
                            mesh,
                            out skeletonPackagePath);
                    skeletonPath =
                        animationSkeleton.GetPathName();
                }

                using var dto =
                    new SkeletalMeshDto(
                        mesh,
                        EMeshQuality.Highest,
                        ENaniteMeshFormat.NoNanite,
                        exportMorphTarget: false);

                var fileName =
                    $"s{converted:D4}.xsk";
                var outPath =
                    Path.Combine(
                        outputDir,
                        fileName);

                var result =
                    WriteXzsk(
                        outPath,
                        dto,
                        animationSkeleton);

                rows.Add(new {
                    index = converted,
                    file = fileName,
                    packagePath = logicalPackage,
                    resolvedPackagePath =
                        resolvedPath,
                    objectPath =
                        mesh.GetPathName(),
                    result.bones,
                    result.vertices,
                    result.indices,
                    result.triangles,
                    result.sections,
                    result.uvChannels,
                    result.maxVertexInfluences,
                    skeletonPackagePath,
                    skeletonPath,
                    selfRig,
                    skeletonHash =
                        result.skeletonHash
                            .ToString("x16"),
                    meshLayoutHash =
                        result.meshLayoutHash
                            .ToString("x16"),
                    result.skeletonBones,
                    result.fileBytes
                });

                converted++;
                if (selfRig)
                    selfRigFallbackCount++;
                totalBones += result.bones;
                totalVertices += result.vertices;
                totalIndices += result.indices;
                totalTriangles += result.triangles;
                totalSections += result.sections;
                totalFileBytes += result.fileBytes;
                maxUvChannels =
                    Math.Max(
                        maxUvChannels,
                        result.uvChannels);
                maxInfluences =
                    Math.Max(
                        maxInfluences,
                        result.maxVertexInfluences);

                var hash =
                    result.skeletonHash
                        .ToString("x16");
                hashes[hash] =
                    hashes.GetValueOrDefault(hash) + 1;

                var meshHash =
                    result.meshLayoutHash
                        .ToString("x16");
                meshLayoutHashes[meshHash] =
                    meshLayoutHashes.GetValueOrDefault(meshHash) + 1;
            }
            catch (Exception e)
            {
                failures.Add(new {
                    packagePath = logicalPackage,
                    objectPath =
                        mesh.GetPathName(),
                    error =
                        e.GetType().FullName +
                        ": " +
                        e.Message
                });
            }
        }
    }
    catch (Exception e)
    {
        failures.Add(new {
            packagePath = logicalPackage,
            error =
                e.GetType().FullName +
                ": " +
                e.Message
        });
    }
}

var ready =
    converted == maxMeshes &&
    rows.Count == maxMeshes &&
    failures.Count == 0 &&
    totalBones > 0 &&
    totalVertices > 0 &&
    totalIndices > 0 &&
    totalTriangles > 0 &&
    totalSections > 0 &&
    totalFileBytes > 0 &&
    maxUvChannels is >= 1 and <= (int)XzskMaxUvs &&
    maxInfluences is >= 1 and <= (int)XzskMaxInfluences;

var report = new {
    schemaVersion = 1,
    format = "xziel_skinned_mesh_xzsk_v2",
    sourceGameName,
    requestedMeshes = maxMeshes,
    convertedMeshes = converted,
    totalBones,
    totalVertices,
    totalIndices,
    totalTriangles,
    totalSections,
    maxUvChannels,
    maxInfluences,
    selfRigFallbackCount,
    skeletonHashCounts = hashes,
    meshLayoutHashCounts = meshLayoutHashes,
    totalFileBytes,
    failureCount = failures.Count,
    meshes = rows,
    failures,
    ready
};

File.WriteAllText(
    Path.Combine(
        outputDir,
        "report.json"),
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_UE_XZSK_PROBE " +
    JsonSerializer.Serialize(new {
        requested = maxMeshes,
        converted,
        totalBones,
        totalVertices,
        totalIndices,
        totalTriangles,
        totalSections,
        maxUvChannels,
        maxInfluences,
        selfRigFallbackCount,
        skeletons = hashes.Count,
        meshLayouts = meshLayoutHashes.Count,
        totalFileBytes,
        failures = failures.Count,
        ready
    }));

foreach (var failure in failures.Take(100))
{
    Console.WriteLine(
        "XZIEL_UE_XZSK_FAILURE " +
        JsonSerializer.Serialize(failure));
}

if (!ready)
{
    Console.WriteLine(
        "XZIEL_UE_XZSK_PROBE_FAILURE");
    return 5;
}

Console.WriteLine(
    "XZIEL_UE_XZSK_PROBE_GREEN");
return 0;

static (
    int bones,
    int vertices,
    int indices,
    int triangles,
    int sections,
    int uvChannels,
    int maxVertexInfluences,
    ulong skeletonHash,
    ulong meshLayoutHash,
    int skeletonBones,
    long fileBytes
) WriteXzsk(
    string outputPath,
    SkeletalMeshDto dto,
    USkeleton? animationSkeleton)
{
    if (dto.Bones.Length == 0)
        throw new InvalidDataException(
            "skeletal mesh has no bones");

    var lod =
        dto.LODs.FirstOrDefault()
        ?? throw new InvalidDataException(
            "skeletal mesh has no usable LOD");

    if (lod.Vertices.Length == 0 ||
        lod.Indices.Length == 0 ||
        lod.Sections.Length == 0)
    {
        throw new InvalidDataException(
            "skeletal mesh highest LOD is empty");
    }

    if ((lod.Indices.Length % 3) != 0)
        throw new InvalidDataException(
            "skeletal mesh index count is not divisible by 3");

    var uvChannels =
        1 + lod.ExtraUvs.Length;

    if (uvChannels > (int)XzskMaxUvs)
        throw new InvalidDataException(
            $"skeletal mesh has {uvChannels} UV channels; max is {XzskMaxUvs}");

    foreach (var extra in lod.ExtraUvs)
    {
        if (extra.Length != lod.Vertices.Length)
            throw new InvalidDataException(
                "skeletal mesh extra UV vertex count mismatch");
    }

    var sections =
        lod.Sections
            .Where(section =>
                section.IsValid &&
                section.NumFaces > 0)
            .ToArray();

    if (sections.Length == 0)
        throw new InvalidDataException(
            "skeletal mesh has no valid sections");

    using SkeletonDto? skeletonDto =
        animationSkeleton is null
            ? null
            : new SkeletonDto(
                animationSkeleton);

    var skeletonBones =
        skeletonDto?.Bones ??
        dto.Bones;

    if (skeletonBones.Length == 0)
        throw new InvalidDataException(
            "linked skeleton has no bones");

    if (skeletonBones.Length > ushort.MaxValue)
        throw new InvalidDataException(
            $"linked skeleton has too many bones: {skeletonBones.Length}");

    var skeletonHash =
        XzielSkeletonIdentity.HashTopology(
            skeletonBones);
    var meshLayoutHash =
        XzielSkeletonIdentity.HashBones(
            dto.Bones);

    var skeletonByName =
        new Dictionary<string, int>(
            StringComparer.OrdinalIgnoreCase);

    for (var i = 0;
         i < skeletonBones.Length;
         ++i)
    {
        var name =
            skeletonBones[i].Name;

        if (!skeletonByName.TryAdd(
                name,
                i))
        {
            throw new InvalidDataException(
                $"linked USkeleton contains duplicate bone name: {name}");
        }
    }

    var meshToSkeleton =
        new uint[dto.Bones.Length];

    for (var i = 0;
         i < dto.Bones.Length;
         ++i)
    {
        var meshBone =
            dto.Bones[i];

        if (!skeletonByName.TryGetValue(
                meshBone.Name,
                out var skeletonIndex))
        {
            throw new InvalidDataException(
                $"mesh bone {i} '{meshBone.Name}' is absent from linked USkeleton");
        }

        var skeletonBone =
            skeletonBones[skeletonIndex];

        if (meshBone.ParentIndex < 0)
        {
            if (skeletonBone.ParentIndex != -1)
            {
                throw new InvalidDataException(
                    $"mesh root bone '{meshBone.Name}' maps to non-root skeleton bone {skeletonIndex}");
            }
        }
        else
        {
            var mappedParent =
                meshToSkeleton[
                    meshBone.ParentIndex];

            if (skeletonBone.ParentIndex !=
                checked((int)mappedParent))
            {
                throw new InvalidDataException(
                    $"mesh bone '{meshBone.Name}' parent remap mismatch: meshParent={meshBone.ParentIndex} skeletonParent={skeletonBone.ParentIndex} mappedParent={mappedParent}");
            }
        }

        meshToSkeleton[i] =
            checked((uint)skeletonIndex);
    }

    var stringData =
        new MemoryStream();
    var boneNames =
        new (uint offset, uint bytes)[
            dto.Bones.Length];

    for (var i = 0;
         i < dto.Bones.Length;
         ++i)
    {
        var encoded =
            Encoding.UTF8.GetBytes(
                dto.Bones[i].Name);

        if (encoded.Length == 0)
            throw new InvalidDataException(
                $"bone {i} has empty name");

        boneNames[i] = (
            checked((uint)stringData.Position),
            checked((uint)encoded.Length));
        stringData.Write(encoded);
    }

    var boneOffset =
        XzskHeaderBytes;
    var vertexOffset =
        checked(
            boneOffset +
            checked((uint)dto.Bones.Length) *
                XzskBoneBytes);
    var indexOffset =
        checked(
            vertexOffset +
            checked((uint)lod.Vertices.Length) *
                XzskVertexBytes);
    var sectionOffset =
        checked(
            indexOffset +
            checked((uint)lod.Indices.Length) *
                4u);
    var stringOffset =
        checked(
            sectionOffset +
            checked((uint)sections.Length) *
                XzskSectionBytes);
    var stringBytes =
        checked((uint)stringData.Length);
    var fileBytes =
        checked(
            (long)stringOffset +
            stringBytes);

    if (fileBytes > uint.MaxValue)
        throw new InvalidDataException(
            $"XZSK v2 file exceeds 32-bit offsets: {fileBytes}");

    var minX = float.PositiveInfinity;
    var minY = float.PositiveInfinity;
    var minZ = float.PositiveInfinity;
    var maxX = float.NegativeInfinity;
    var maxY = float.NegativeInfinity;
    var maxZ = float.NegativeInfinity;
    var maxVertexInfluences = 0;

    foreach (var vertex in lod.Vertices)
    {
        var position =
            XzielSkeletonIdentity.PositionToXziel(
                vertex.Position);

        if (!float.IsFinite(position.X) ||
            !float.IsFinite(position.Y) ||
            !float.IsFinite(position.Z))
        {
            throw new InvalidDataException(
                "skeletal vertex position is non-finite");
        }

        minX = Math.Min(minX, position.X);
        minY = Math.Min(minY, position.Y);
        minZ = Math.Min(minZ, position.Z);
        maxX = Math.Max(maxX, position.X);
        maxY = Math.Max(maxY, position.Y);
        maxZ = Math.Max(maxZ, position.Z);

        var influences =
            vertex.Influences
                .Where(x => x.RawWeight != 0)
                .ToArray();

        if (influences.Length == 0)
            throw new InvalidDataException(
                "skeletal vertex has zero bone influences");

        if (influences.Length > (int)XzskMaxInfluences)
            throw new InvalidDataException(
                $"skeletal vertex has {influences.Length} influences; max is {XzskMaxInfluences}");

        maxVertexInfluences =
            Math.Max(
                maxVertexInfluences,
                influences.Length);

        foreach (var influence in influences)
        {
            if (influence.Bone >= dto.Bones.Length)
                throw new InvalidDataException(
                    $"skeletal vertex bone index {influence.Bone} >= {dto.Bones.Length}");
        }
    }

    foreach (var index in lod.Indices)
    {
        if (index >= lod.Vertices.Length)
            throw new InvalidDataException(
                $"skeletal index {index} >= vertex count {lod.Vertices.Length}");
    }

    foreach (var section in sections)
    {
        var first =
            checked((uint)section.FirstIndex);
        var count =
            checked((uint)section.NumFaces * 3u);

        if ((ulong)first + count >
            (ulong)lod.Indices.Length)
        {
            throw new InvalidDataException(
                "skeletal section index range exceeds LOD index buffer");
        }
    }

    Directory.CreateDirectory(
        Path.GetDirectoryName(
            Path.GetFullPath(
                outputPath))!);

    using var stream =
        new FileStream(
            outputPath,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None);
    using var writer =
        new BinaryWriter(
            stream,
            Encoding.UTF8,
            leaveOpen: true);

    writer.Write((byte)'X');
    writer.Write((byte)'Z');
    writer.Write((byte)'S');
    writer.Write((byte)'K');
    writer.Write(XzskVersion);
    writer.Write(
        FlagXzielBasis |
        FlagIndexU32 |
        FlagSkeletonRemap);
    writer.Write(
        checked((uint)dto.Bones.Length));
    writer.Write(
        checked((uint)lod.Vertices.Length));
    writer.Write(
        checked((uint)lod.Indices.Length));
    writer.Write(
        checked((uint)sections.Length));
    writer.Write(XzskBoneBytes);
    writer.Write(XzskVertexBytes);
    writer.Write(XzskSectionBytes);
    writer.Write(boneOffset);
    writer.Write(vertexOffset);
    writer.Write(indexOffset);
    writer.Write(sectionOffset);
    writer.Write(stringOffset);
    writer.Write(stringBytes);
    writer.Write(skeletonHash);
    writer.Write(minX);
    writer.Write(minY);
    writer.Write(minZ);
    writer.Write(maxX);
    writer.Write(maxY);
    writer.Write(maxZ);
    writer.Write(
        checked((uint)skeletonBones.Length));
    writer.Write(0u);
    writer.Write(meshLayoutHash);

    if (stream.Position != XzskHeaderBytes)
        throw new InvalidDataException(
            $"XZSK header size mismatch: {stream.Position}");

    for (var i = 0;
         i < dto.Bones.Length;
         ++i)
    {
        var bone = dto.Bones[i];
        var rotation =
            XzielSkeletonIdentity.RotationToXziel(
                bone.Transform.Rotation);
        var translation =
            XzielSkeletonIdentity.PositionToXziel(
                bone.Transform.Translation);
        var scale =
            bone.Transform.Scale3D;

        writer.Write(bone.ParentIndex);
        writer.Write(boneNames[i].offset);
        writer.Write(boneNames[i].bytes);
        writer.Write(meshToSkeleton[i]);

        writer.Write(rotation.X);
        writer.Write(rotation.Y);
        writer.Write(rotation.Z);
        writer.Write(rotation.W);

        writer.Write(translation.X);
        writer.Write(translation.Y);
        writer.Write(translation.Z);

        writer.Write(scale.X);
        writer.Write(scale.Y);
        writer.Write(scale.Z);
    }

    for (var vertexIndex = 0;
         vertexIndex < lod.Vertices.Length;
         ++vertexIndex)
    {
        var vertex =
            lod.Vertices[vertexIndex];
        var position =
            XzielSkeletonIdentity.PositionToXziel(
                vertex.Position);
        var normal =
            XzielSkeletonIdentity.DirectionToXziel(
                new FVector(
                    vertex.Normal.X,
                    vertex.Normal.Y,
                    vertex.Normal.Z));
        var tangent =
            XzielSkeletonIdentity.TangentToXziel(
                vertex.Tangent);

        writer.Write(position.X);
        writer.Write(position.Y);
        writer.Write(position.Z);

        writer.Write(normal.X);
        writer.Write(normal.Y);
        writer.Write(normal.Z);

        writer.Write(tangent.X);
        writer.Write(tangent.Y);
        writer.Write(tangent.Z);
        writer.Write(tangent.W);

        writer.Write(vertex.Uv.U);
        writer.Write(vertex.Uv.V);

        for (var channel = 1;
             channel < (int)XzskMaxUvs;
             ++channel)
        {
            if (channel - 1 <
                lod.ExtraUvs.Length)
            {
                var uv =
                    lod.ExtraUvs[
                        channel - 1][
                        vertexIndex];
                writer.Write(uv.U);
                writer.Write(uv.V);
            }
            else
            {
                writer.Write(0.0f);
                writer.Write(0.0f);
            }
        }

        var influences =
            vertex.Influences
                .Where(x => x.RawWeight != 0)
                .ToArray();

        for (var i = 0;
             i < (int)XzskMaxInfluences;
             ++i)
        {
            writer.Write(
                i < influences.Length
                    ? influences[i].Bone
                    : (ushort)0);
        }

        for (var i = 0;
             i < (int)XzskMaxInfluences;
             ++i)
        {
            writer.Write(
                i < influences.Length
                    ? influences[i].RawWeight
                    : (ushort)0);
        }
    }

    for (var i = 0;
         i < lod.Indices.Length;
         i += 3)
    {
        writer.Write(lod.Indices[i]);
        writer.Write(lod.Indices[i + 2]);
        writer.Write(lod.Indices[i + 1]);
    }

    foreach (var section in sections)
    {
        writer.Write(
            checked((uint)section.FirstIndex));
        writer.Write(
            checked((uint)section.NumFaces * 3u));
        writer.Write(
            checked((uint)section.MaterialIndex));
        writer.Write(
            section.CastShadow
                ? 1u
                : 0u);
    }

    writer.Write(stringData.ToArray());
    writer.Flush();

    if (stream.Length != fileBytes)
        throw new InvalidDataException(
            $"XZSK size mismatch expected={fileBytes} actual={stream.Length}");

    return (
        dto.Bones.Length,
        lod.Vertices.Length,
        lod.Indices.Length,
        lod.Indices.Length / 3,
        sections.Length,
        uvChannels,
        maxVertexInfluences,
        skeletonHash,
        meshLayoutHash,
        skeletonBones.Length,
        fileBytes);
}

static USkeleton ResolveMeshSkeleton(
    DefaultFileProvider provider,
    USkeletalMesh mesh,
    out string sourcePackagePath)
{
    var resolved =
        mesh.Skeleton.ResolvedObjectNoCache
        ?? throw new InvalidDataException(
            "skeletal mesh has no resolvable Skeleton object reference");

    var objectPath =
        resolved.GetPathName();

    if (string.IsNullOrWhiteSpace(
            objectPath))
    {
        throw new InvalidDataException(
            "skeletal mesh Skeleton reference has no object path");
    }

    var dot =
        objectPath.LastIndexOf('.');
    var virtualPackagePath =
        (dot > 0
            ? objectPath[..dot]
            : objectPath)
        .Replace('\\', '/')
        .Trim();

    var objectName =
        dot > 0 &&
        dot + 1 < objectPath.Length
            ? objectPath[(dot + 1)..]
            : virtualPackagePath
                .Split('/')
                .Last();

    var normalizedVirtual =
        virtualPackagePath
            .TrimStart('/');

    var candidates =
        new List<string>
        {
            normalizedVirtual + ".uasset"
        };

    var firstSlash =
        normalizedVirtual
            .IndexOf('/');

    if (firstSlash > 0 &&
        firstSlash + 1 <
            normalizedVirtual.Length)
    {
        var mountName =
            normalizedVirtual[
                ..firstSlash];
        var mountRelative =
            normalizedVirtual[
                (firstSlash + 1)..];

        if (mountName.Equals(
                "Game",
                StringComparison.OrdinalIgnoreCase))
        {
            candidates.Add(
                $"Content/{mountRelative}.uasset");
        }
        else if (mountName.Equals(
                     "Engine",
                     StringComparison.OrdinalIgnoreCase))
        {
            candidates.Add(
                $"Engine/Content/{mountRelative}.uasset");
        }
        else
        {
            candidates.Add(
                $"Plugins/{mountName}/Content/{mountRelative}.uasset");
        }
    }

    string? providerKey = null;

    foreach (var suffix in
             candidates.Distinct(
                 StringComparer.OrdinalIgnoreCase))
    {
        var matches =
            provider.Files.Keys
                .Where(key =>
                    key.EndsWith(
                        suffix,
                        StringComparison.OrdinalIgnoreCase))
                .OrderBy(
                    key => key.Length)
                .ThenBy(
                    key => key,
                    StringComparer.OrdinalIgnoreCase)
                .Take(2)
                .ToArray();

        if (matches.Length == 1)
        {
            providerKey = matches[0];
            break;
        }

        if (matches.Length > 1)
        {
            throw new InvalidDataException(
                $"ambiguous Skeleton package resolution for {objectPath}: " +
                string.Join(", ", matches));
        }
    }

    if (providerKey is null)
    {
        throw new FileNotFoundException(
            $"Skeleton package unresolved for {objectPath}; tried " +
            string.Join(", ", candidates));
    }

    sourcePackagePath =
        providerKey;

    var package =
        provider.LoadPackage(
            providerKey);

    var skeletons =
        package.GetExports()
            .OfType<USkeleton>()
            .ToArray();

    var exact =
        skeletons
            .Where(skeleton =>
                string.Equals(
                    skeleton.Name,
                    objectName,
                    StringComparison.OrdinalIgnoreCase))
            .ToArray();

    if (exact.Length == 1)
        return exact[0];

    if (exact.Length > 1)
    {
        throw new InvalidDataException(
            $"multiple Skeleton exports named {objectName} in {providerKey}");
    }

    if (skeletons.Length == 1)
        return skeletons[0];

    throw new InvalidDataException(
        $"Skeleton export {objectName} unresolved in {providerKey}; decoded skeleton exports={skeletons.Length}");
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

    var slash =
        normalized.IndexOf('/');

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

static string? ResolveProviderPackagePath(
    DefaultFileProvider provider,
    string logicalPath)
{
    var normalized =
        logicalPath
            .Replace('\\', '/')
            .TrimStart('/');

    if (provider.Files.ContainsKey(
            normalized))
        return normalized;

    var matches =
        provider.Files.Keys
            .Where(key =>
                key.EndsWith(
                    normalized,
                    StringComparison.OrdinalIgnoreCase))
            .OrderBy(
                key => key.Length)
            .ThenBy(
                key => key,
                StringComparer.OrdinalIgnoreCase)
            .Take(2)
            .ToArray();

    return matches.Length == 1
        ? matches[0]
        : null;
}
