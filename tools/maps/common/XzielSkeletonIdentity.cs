using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse_Conversion.Dto;
using System.Buffers.Binary;
using System.Text;

internal static class XzielSkeletonIdentity
{
    private const ulong FnvOffset = 14695981039346656037UL;
    private const ulong FnvPrime = 1099511628211UL;

    public static FVector PositionToXziel(
        FVector value)
        => new(
            value.X * 0.01f,
            -value.Y * 0.01f,
            value.Z * 0.01f);

    public static FVector DirectionToXziel(
        FVector value)
        => new(
            value.X,
            -value.Y,
            value.Z);

    public static FVector4 TangentToXziel(
        FVector4 value)
        => new(
            value.X,
            -value.Y,
            value.Z,
            -value.W);

    public static FQuat RotationToXziel(
        FQuat value)
        => new(
            -value.X,
            value.Y,
            -value.Z,
            value.W);

    public static ulong HashBones(
        IReadOnlyList<MeshBoneDto> bones)
    {
        if (bones.Count == 0)
            throw new InvalidDataException(
                "skeleton has no bones");

        ulong hash = FnvOffset;

        AppendU32(
            ref hash,
            checked((uint)bones.Count));

        for (var i = 0;
             i < bones.Count;
             ++i)
        {
            var bone = bones[i];

            if (bone.ParentIndex < -1 ||
                (bone.ParentIndex >= 0 &&
                 bone.ParentIndex >= i))
            {
                throw new InvalidDataException(
                    $"invalid skeleton parent at bone {i}: {bone.ParentIndex}");
            }

            var nameBytes =
                Encoding.UTF8.GetBytes(
                    bone.Name ?? string.Empty);

            if (nameBytes.Length == 0)
                throw new InvalidDataException(
                    $"bone {i} has empty name");

            AppendU32(
                ref hash,
                checked((uint)nameBytes.Length));
            Append(
                ref hash,
                nameBytes);
            AppendI32(
                ref hash,
                bone.ParentIndex);

            var position =
                PositionToXziel(
                    bone.Transform.Translation);
            var rotation =
                RotationToXziel(
                    bone.Transform.Rotation);
            var scale =
                bone.Transform.Scale3D;

            AppendFloat(ref hash, position.X);
            AppendFloat(ref hash, position.Y);
            AppendFloat(ref hash, position.Z);

            AppendFloat(ref hash, rotation.X);
            AppendFloat(ref hash, rotation.Y);
            AppendFloat(ref hash, rotation.Z);
            AppendFloat(ref hash, rotation.W);

            AppendFloat(ref hash, scale.X);
            AppendFloat(ref hash, scale.Y);
            AppendFloat(ref hash, scale.Z);
        }

        return hash == 0UL
            ? FnvOffset
            : hash;
    }

    private static void AppendFloat(
        ref ulong hash,
        float value)
    {
        if (!float.IsFinite(value))
            throw new InvalidDataException(
                "skeleton transform contains non-finite value");

        AppendU32(
            ref hash,
            BitConverter.SingleToUInt32Bits(
                value));
    }

    private static void AppendI32(
        ref ulong hash,
        int value)
        => AppendU32(
            ref hash,
            unchecked((uint)value));

    private static void AppendU32(
        ref ulong hash,
        uint value)
    {
        Span<byte> bytes =
            stackalloc byte[4];

        BinaryPrimitives.WriteUInt32LittleEndian(
            bytes,
            value);

        Append(
            ref hash,
            bytes);
    }

    private static void Append(
        ref ulong hash,
        ReadOnlySpan<byte> bytes)
    {
        foreach (var value in bytes)
        {
            hash ^= value;
            hash *= FnvPrime;
        }
    }
}
