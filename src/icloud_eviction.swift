import Darwin
import Foundation

struct Item: Codable {
    let path: String
    let identity: [Int64]?
}

struct Result: Codable {
    let status: String
    let detail: String
}

func identity(_ path: String) throws -> [Int64] {
    var info = stat()
    guard lstat(path, &info) == 0 else {
        throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno))
    }
    guard (info.st_mode & S_IFMT) == S_IFREG else {
        throw NSError(domain: "HAP", code: 1, userInfo: [NSLocalizedDescriptionKey: "Not a regular file"])
    }
    return [
        Int64(info.st_dev), Int64(info.st_ino), Int64(info.st_size),
        Int64(info.st_mtimespec.tv_sec) * 1_000_000_000 + Int64(info.st_mtimespec.tv_nsec),
        Int64(info.st_ctimespec.tv_sec) * 1_000_000_000 + Int64(info.st_ctimespec.tv_nsec)
    ]
}

func process(_ item: Item, evict: Bool) -> Result {
    do {
        let currentIdentity = try identity(item.path)
        if evict && currentIdentity != item.identity {
            return Result(status: "unsafe", detail: "File changed after backup verification")
        }
        let url = URL(fileURLWithPath: item.path)
        let values = try url.resourceValues(forKeys: [
            .isUbiquitousItemKey, .ubiquitousItemIsUploadedKey,
            .ubiquitousItemIsUploadingKey, .ubiquitousItemHasUnresolvedConflictsKey,
            .ubiquitousItemIsExcludedFromSyncKey, .ubiquitousItemDownloadingStatusKey,
            .ubiquitousItemIsDownloadingKey
        ])
        guard values.isUbiquitousItem == true,
              values.ubiquitousItemIsUploaded == true,
              values.ubiquitousItemIsUploading == false,
              values.ubiquitousItemHasUnresolvedConflicts == false,
              values.ubiquitousItemIsExcludedFromSync == false,
              values.ubiquitousItemIsDownloading == false else {
            return Result(status: "unsafe", detail: "iCloud upload or sync state is not safe")
        }
        if values.ubiquitousItemDownloadingStatus == .notDownloaded {
            return Result(status: "cloud_only", detail: "")
        }
        guard values.ubiquitousItemDownloadingStatus == .current else {
            return Result(status: "unsafe", detail: "Local iCloud version is not current")
        }
        if evict {
            guard try identity(item.path) == currentIdentity else {
                return Result(status: "unsafe", detail: "File changed while checking iCloud state")
            }
            try FileManager.default.evictUbiquitousItem(at: url)
            return Result(status: "evicted", detail: "")
        }
        return Result(status: "eligible", detail: "")
    } catch {
        return Result(status: "error", detail: error.localizedDescription)
    }
}

do {
    guard CommandLine.arguments.count == 2,
          ["inspect", "evict"].contains(CommandLine.arguments[1]) else {
        throw NSError(domain: "HAP", code: 2, userInfo: [NSLocalizedDescriptionKey: "Expected inspect or evict"])
    }
    let items = try JSONDecoder().decode([Item].self, from: FileHandle.standardInput.readDataToEndOfFile())
    let results = items.map { process($0, evict: CommandLine.arguments[1] == "evict") }
    FileHandle.standardOutput.write(try JSONEncoder().encode(results))
} catch {
    FileHandle.standardError.write(Data("iCloud helper failed: \(error.localizedDescription)\n".utf8))
    exit(1)
}
