using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Versions;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

if (args.Length != 4)
{
    Console.Error.WriteLine(
        "usage: NachtLightmapTextureExtractor <unpacked-root> <baked-census.json> <output.xzlt> <report.json>");
    return 2;
}

string ExportNameFromPath(string path)
{
    var text = path.Replace('\\', '/').Trim();
    var colon = text.LastIndexOf(':');
    if (colon >= 0 && colon + 1 < text.Length)
        return text[(colon + 1)..];

    var slash = text.LastIndexOf('/');
    var tail = slash >= 0 ? text[(slash + 1)..] : text;
    var dot = tail.LastIndexOf('.');
    return dot >= 0 && dot + 1 < tail.Length
        ? tail[(dot + 1)..]
        : tail;
}

using var censusDoc =
    JsonDocument.Parse(
        File.ReadAllText(args[1]));

var wantedPaths =
    censusDoc.RootElement
        .GetProperty("lightmapTextures")
        .EnumerateArray()
        .Select(x => x.GetString() ?? "")
        .Where(x => !string.IsNullOrWhiteSpace(x))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x, StringComparer.Ordinal)
        .ToArray();

if (wantedPaths.Length != 188)
{
    Console.Error.WriteLine(
        $"expected 188 unique lightmap textures, got {wantedPaths.Length}");
    return 3;
}

var wantedByName =
    new Dictionary<string, string>(
        StringComparer.OrdinalIgnoreCase);

foreach (var path in wantedPaths)
{
    var name = ExportNameFromPath(path);
    if (string.IsNullOrWhiteSpace(name))
    {
        Console.Error.WriteLine(
            $"could not derive export name from {path}");
        return 4;
    }

    if (!wantedByName.TryAdd(name, path))
    {
        Console.Error.WriteLine(
            $"duplicate lightmap export name {name}");
        return 5;
    }
}

var provider =
    new DefaultFileProvider(
        args[0],
        SearchOption.AllDirectories,
        true,
        new VersionContainer(EGame.GAME_UE4_21));

provider.Initialize();
provider.PostMount();
provider.LoadVirtualPaths();

var builtDataCandidates =
    provider.Files.Values
        .Where(f => f.IsUePackage)
        .Select(f => f.Path)
        .Where(
            path =>
                path.EndsWith(
                    ".uasset",
                    StringComparison.OrdinalIgnoreCase)
                && path.Contains(
                    "BuiltData",
                    StringComparison.OrdinalIgnoreCase)
                && (path.Contains(
                        "UGC2755515831",
                        StringComparison.OrdinalIgnoreCase)
                    || path.Contains(
                        "Nacht",
                        StringComparison.OrdinalIgnoreCase)))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderBy(x => x)
        .ToArray();

if (builtDataCandidates.Length == 0)
{
    Console.Error.WriteLine(
        "no Nacht BuiltData package candidates");
    return 6;
}

var textures =
    new Dictionary<string, UTexture2D>(
        StringComparer.OrdinalIgnoreCase);

foreach (var candidate in builtDataCandidates)
{
    try
    {
        foreach (
            var texture in
            provider.LoadPackage(candidate)
                .GetExports()
                .OfType<UTexture2D>())
        {
            if (!wantedByName.ContainsKey(texture.Name))
                continue;

            if (!textures.TryAdd(texture.Name, texture))
            {
                Console.Error.WriteLine(
                    $"duplicate resolved texture export {texture.Name}");
                return 7;
            }
        }
    }
    catch (Exception e)
    {
        Console.Error.WriteLine(
            $"BuiltData load failed {candidate}: {e.Message}");
        return 8;
    }
}

var missingNames =
    wantedByName.Keys
        .Where(name => !textures.ContainsKey(name))
        .OrderBy(x => x)
        .ToArray();

if (missingNames.Length != 0)
{
    Console.Error.WriteLine(
        "missing lightmap exports: "
        + string.Join(", ", missingNames.Take(16)));
    return 9;
}

var textureRows = new List<TextureRow>();
var mipRows = new List<MipRow>();
ulong payloadBytes = 0;

for (var textureIndex = 0;
     textureIndex < wantedPaths.Length;
     ++textureIndex)
{
    var sourcePath = wantedPaths[textureIndex];
    var exportName = ExportNameFromPath(sourcePath);
    var texture = textures[exportName];
    var formatName = texture.Format.ToString();

    uint format;
    int blockBytes;

    if (formatName == "PF_DXT1")
    {
        format = 1u;
        blockBytes = 8;
    }
    else if (formatName == "PF_DXT5")
    {
        format = 2u;
        blockBytes = 16;
    }
    else
    {
        Console.Error.WriteLine(
            $"unsupported lightmap format {formatName} for {exportName}");
        return 10;
    }

    if (texture.PlatformData.Mips.Length == 0)
    {
        Console.Error.WriteLine(
            $"texture has no mips: {exportName}");
        return 11;
    }

    var firstMip = mipRows.Count;
    ulong textureBytes = 0;

    for (var mipIndex = 0;
         mipIndex < texture.PlatformData.Mips.Length;
         ++mipIndex)
    {
        var mip = texture.GetMip(mipIndex);
        var bytes = mip?.BulkData?.Data;

        if (mip is null || bytes is null || bytes.Length == 0)
        {
            Console.Error.WriteLine(
                $"missing mip payload {exportName} mip={mipIndex}");
            return 12;
        }

        if (mip.SizeX <= 0 || mip.SizeY <= 0)
        {
            Console.Error.WriteLine(
                $"invalid mip dimensions {exportName} mip={mipIndex}");
            return 13;
        }

        var blocksX = (mip.SizeX + 3) / 4;
        var blocksY = (mip.SizeY + 3) / 4;
        var expectedBytes =
            checked(blocksX * blocksY * blockBytes);

        if (bytes.Length != expectedBytes)
        {
            Console.Error.WriteLine(
                $"compressed mip size mismatch {exportName} mip={mipIndex}"
                + $" format={formatName} size={mip.SizeX}x{mip.SizeY}"
                + $" bytes={bytes.Length} expected={expectedBytes}");
            return 14;
        }

        if (payloadBytes > uint.MaxValue)
        {
            Console.Error.WriteLine(
                "XZLT payload exceeds 32-bit offset space");
            return 15;
        }

        mipRows.Add(
            new MipRow(
                checked((uint)payloadBytes),
                checked((uint)bytes.Length),
                checked((uint)mip.SizeX),
                checked((uint)mip.SizeY),
                bytes));

        payloadBytes +=
            checked((uint)bytes.Length);
        textureBytes +=
            checked((uint)bytes.Length);
    }

    textureRows.Add(
        new TextureRow(
            sourcePath,
            texture.GetPathName() ?? "",
            exportName,
            formatName,
            format,
            checked((uint)texture.PlatformData.SizeX),
            checked((uint)texture.PlatformData.SizeY),
            checked((uint)firstMip),
            checked((uint)(mipRows.Count - firstMip)),
            texture.SRGB,
            textureBytes));
}

const uint headerBytes = 32u;
const uint textureRecordBytes = 24u;
const uint mipRecordBytes = 16u;

var textureTableOffset = headerBytes;
var mipTableOffset =
    checked(
        textureTableOffset
        + (uint)textureRows.Count * textureRecordBytes);
var payloadOffset =
    checked(
        mipTableOffset
        + (uint)mipRows.Count * mipRecordBytes);

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(args[2]))!);

using (var stream = File.Create(args[2]))
using (var writer = new BinaryWriter(
           stream,
           Encoding.UTF8,
           leaveOpen: false))
{
    writer.Write(
        new byte[] {
            (byte)'X',
            (byte)'Z',
            (byte)'L',
            (byte)'T'
        });
    writer.Write((uint)1);
    writer.Write(checked((uint)textureRows.Count));
    writer.Write(checked((uint)mipRows.Count));
    writer.Write(textureRecordBytes);
    writer.Write(mipRecordBytes);
    writer.Write(textureTableOffset);
    writer.Write(mipTableOffset);

    foreach (var row in textureRows)
    {
        writer.Write(row.Format);
        writer.Write(row.Width);
        writer.Write(row.Height);
        writer.Write(row.FirstMip);
        writer.Write(row.MipCount);
        writer.Write(row.Srgb ? 1u : 0u);
    }

    foreach (var mip in mipRows)
    {
        writer.Write(mip.PayloadOffset);
        writer.Write(mip.Bytes);
        writer.Write(mip.Width);
        writer.Write(mip.Height);
    }

    if (stream.Position != payloadOffset)
    {
        Console.Error.WriteLine(
            $"XZLT table size drift position={stream.Position} expected={payloadOffset}");
        return 16;
    }

    foreach (var mip in mipRows)
        writer.Write(mip.Data);
}

var outputFile = new FileInfo(args[2]);

using var shaStream = File.OpenRead(args[2]);
var sha256 =
    Convert.ToHexString(
        SHA256.HashData(shaStream));

var formatCounts =
    textureRows
        .GroupBy(x => x.FormatName)
        .ToDictionary(
            g => g.Key,
            g => g.Count(),
            StringComparer.Ordinal);

var dimensionCounts =
    textureRows
        .GroupBy(x => $"{x.Width}x{x.Height}")
        .ToDictionary(
            g => g.Key,
            g => g.Count(),
            StringComparer.Ordinal);

var report = new {
    schemaVersion = 1,
    format = "XZLT",
    version = 1,
    sourceCompressionPreserved = true,
    textureCount = textureRows.Count,
    mipCount = mipRows.Count,
    headerBytes,
    textureRecordBytes,
    mipRecordBytes,
    textureTableOffset,
    mipTableOffset,
    payloadOffset,
    payloadBytes,
    fileBytes = outputFile.Length,
    sha256,
    formatCounts,
    dimensionCounts,
    srgbTextureCount =
        textureRows.Count(x => x.Srgb),
    linearTextureCount =
        textureRows.Count(x => !x.Srgb),
    textures =
        textureRows.Select(
            (x, index) => new {
                textureIndex = index,
                x.SourcePath,
                x.ExportPath,
                x.ExportName,
                x.FormatName,
                x.Width,
                x.Height,
                x.FirstMip,
                x.MipCount,
                x.Srgb,
                x.CompressedBytes
            }).ToArray()
};

Directory.CreateDirectory(
    Path.GetDirectoryName(
        Path.GetFullPath(args[3]))!);

File.WriteAllText(
    args[3],
    JsonSerializer.Serialize(
        report,
        new JsonSerializerOptions {
            WriteIndented = true
        }));

Console.WriteLine(
    "XZIEL_NACHT_XZLT_OK "
    + JsonSerializer.Serialize(
        new {
            report.textureCount,
            report.mipCount,
            report.payloadBytes,
            report.fileBytes,
            report.sha256,
            report.formatCounts,
            report.dimensionCounts,
            report.srgbTextureCount,
            report.linearTextureCount
        }));

return 0;

record TextureRow(
    string SourcePath,
    string ExportPath,
    string ExportName,
    string FormatName,
    uint Format,
    uint Width,
    uint Height,
    uint FirstMip,
    uint MipCount,
    bool Srgb,
    ulong CompressedBytes);

record MipRow(
    uint PayloadOffset,
    uint Bytes,
    uint Width,
    uint Height,
    byte[] Data);
