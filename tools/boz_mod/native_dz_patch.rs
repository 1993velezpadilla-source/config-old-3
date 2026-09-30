use dzip::codec::{self, Compression};
use dzip::format::{CHUNK_COMBUF, CHUNK_DZ, CHUNK_ZERO};
use dzip::reader::DzipReader;
use dzip::Archive;
use std::env;
use std::fs;
use std::io::Cursor;
use std::path::Path;

fn norm(s: &str) -> String {
    s.replace('\\', "/").trim_matches('/').to_ascii_lowercase()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 5 {
        eprintln!("usage: native_dz_patch <input.dz> <entry> <replacement> <output.dz>");
        std::process::exit(2);
    }
    let input = &args[1];
    let wanted = norm(&args[2]);
    let replacement_path = &args[3];
    let output = &args[4];

    let original = fs::read(input)?;
    let replacement = fs::read(replacement_path)?;

    let mut reader = DzipReader::new(Cursor::new(original.clone()));
    let archive_settings = reader.read_archive_settings()?;
    let file_count = archive_settings.num_user_files as usize;
    let string_count = file_count
        .checked_add(archive_settings.num_directories as usize)
        .and_then(|v| v.checked_sub(1))
        .ok_or("invalid string count")?;
    let strings = reader.read_strings(string_count)?;
    let file_map = reader.read_file_chunk_map(file_count)?;
    let chunk_settings = reader.read_chunk_settings()?;
    let chunk_table_pos = reader.position()? as usize;
    let chunks = reader.read_chunks(chunk_settings.num_chunks as usize)?;
    let _volumes = reader.read_file_list(chunk_settings.num_archive_files.saturating_sub(1) as usize)?;
    let range_settings = if chunks.iter().any(|c| c.flags & CHUNK_DZ != 0) {
        Some(reader.read_global_settings()?)
    } else {
        None
    };

    let mut target_chunk_id: Option<usize> = None;
    let mut resolved_path = String::new();

    for (i, (dir_id, chunk_ids)) in file_map.iter().enumerate() {
        let file_name = strings.get(i).ok_or("missing file name")?;
        let mut path = String::new();
        if *dir_id > 0 {
            let directory_index = file_count + (*dir_id as usize - 1);
            let directory = strings.get(directory_index).ok_or("invalid directory id")?;
            path.push_str(directory);
            if !path.ends_with('/') && !path.ends_with('\\') {
                path.push('/');
            }
        }
        path.push_str(file_name);

        if norm(&path) == wanted {
            if chunk_ids.len() != 1 {
                return Err(format!("target uses {} chunks; single-chunk patcher required", chunk_ids.len()).into());
            }
            target_chunk_id = Some(chunk_ids[0] as usize);
            resolved_path = path;
            break;
        }
    }

    let chunk_id = target_chunk_id.ok_or_else(|| format!("entry not found: {}", args[2]))?;
    let chunk = *chunks.get(chunk_id).ok_or("invalid target chunk id")?;
    if chunk.file != 0 {
        return Err("target is stored in an auxiliary volume".into());
    }
    if chunk.flags & CHUNK_DZ == 0 || chunk.flags & (CHUNK_ZERO | CHUNK_COMBUF) != 0 {
        return Err(format!("target chunk flags are not standalone DZ: 0x{:x}", chunk.flags).into());
    }

    let settings = range_settings.ok_or("DZ archive has no global range settings")?;
    let encoded = codec::encode(Compression::Dz, &replacement, settings)?;

    let next_offset = chunks
        .iter()
        .filter(|c| c.file == chunk.file)
        .filter(|c| c.flags & CHUNK_ZERO == 0)
        .filter(|c| c.compressed_length > 0)
        .map(|c| c.offset as usize)
        .filter(|&off| off > chunk.offset as usize)
        .min()
        .unwrap_or(original.len());

    let start = chunk.offset as usize;
    let slot = next_offset.checked_sub(start).ok_or("invalid physical slot")?;
    if encoded.len() > slot {
        return Err(format!(
            "native DZ replacement does not fit: encoded={} slot={} old_header_packed={}",
            encoded.len(), slot, chunk.compressed_length
        ).into());
    }

    let mut patched = original;
    patched[start..start + encoded.len()].copy_from_slice(&encoded);
    for b in &mut patched[start + encoded.len()..start + slot] {
        *b = 0;
    }

    let meta = chunk_table_pos + chunk_id * 16;
    if meta + 16 > patched.len() {
        return Err("chunk metadata offset out of range".into());
    }
    patched[meta + 4..meta + 8].copy_from_slice(&(encoded.len() as u32).to_le_bytes());
    patched[meta + 8..meta + 12].copy_from_slice(&(replacement.len() as u32).to_le_bytes());

    if let Some(parent) = Path::new(output).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(output, &patched)?;

    let mut verify = Archive::open_path(output)?;
    let decoded = verify.read_entry_by_path(&resolved_path)?;
    if decoded != replacement {
        return Err("patched archive decoded bytes do not match replacement".into());
    }

    println!("XZIEL_BOZ_NATIVE_DZ_INPLACE_PATCH_OK");
    println!("entry={}", resolved_path.replace('\\', "/"));
    println!("chunk_id={chunk_id}");
    println!("offset=0x{:x}", chunk.offset);
    println!("old_header_packed={}", chunk.compressed_length);
    println!("physical_slot={slot}");
    println!("new_packed={}", encoded.len());
    println!("unpacked={}", replacement.len());
    println!("flags=0x{:x}", chunk.flags);
    Ok(())
}
