import Foundation
import XCTest

@testable import notchPocket

@MainActor
final class ShelfPersistenceIsolationTests: XCTestCase {
    private enum FixtureError: Error {
        case preexistingDirectory
    }

    private func directory() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("notch-shelf-tests-\(UUID().uuidString)", isDirectory: true)
        guard !FileManager.default.fileExists(atPath: directory.path) else {
            throw FixtureError.preexistingDirectory
        }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        addTeardownBlock {
            try FileManager.default.removeItem(at: directory)
            XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
        }
        return directory
    }

    private func itemsFile(in directory: URL) -> URL {
        directory.appendingPathComponent("items.json")
    }

    func testMissingFixtureFileLoadsEmptyWithoutCreatingAnIndex() throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)

        XCTAssertTrue(service.load().isEmpty)

        XCTAssertFalse(FileManager.default.fileExists(atPath: itemsFile(in: directory).path))
    }

    func testSaveUsesOwnedDirectoryAndRawJSONPreservesAllItemKinds() throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)
        let link = try XCTUnwrap(URL(string: "https://example.invalid/fixture"))
        let bookmark = Data([1, 2, 3, 4])
        let items = [
            ShelfItem(kind: .text(string: "synthetic text")),
            ShelfItem(kind: .link(url: link)),
            ShelfItem(kind: .file(bookmark: bookmark), isTemporary: true)
        ]

        service.save(items)

        let bytes = try Data(contentsOf: itemsFile(in: directory))
        let stored = try XCTUnwrap(JSONSerialization.jsonObject(with: bytes) as? [[String: Any]])
        XCTAssertEqual(stored.count, 3)
        XCTAssertEqual(stored.map { $0["id"] as? String }, items.map { $0.id.uuidString })
        XCTAssertEqual((stored[0]["kind"] as? [String: Any])?["value"] as? String, "synthetic text")
        XCTAssertEqual((stored[1]["kind"] as? [String: Any])?["value"] as? String, link.absoluteString)
        XCTAssertEqual((stored[2]["kind"] as? [String: Any])?["value"] as? String, bookmark.base64EncodedString())
        XCTAssertEqual(stored[2]["isTemporary"] as? Bool, true)
        XCTAssertEqual(try ShelfPersistenceService(storageDirectory: directory).load(), items)
    }

    func testDistinctDirectoriesNeverReadOrOverwriteEachOther() throws {
        let first = try directory()
        let second = try directory()
        let firstStore = try ShelfPersistenceService(storageDirectory: first)
        let secondStore = try ShelfPersistenceService(storageDirectory: second)
        let firstItems = [ShelfItem(kind: .text(string: "first fixture"))]
        let secondItems = [ShelfItem(kind: .text(string: "second fixture"))]
        firstStore.save(firstItems)
        let firstBytes = try Data(contentsOf: itemsFile(in: first))

        secondStore.save(secondItems)

        XCTAssertEqual(firstStore.load(), firstItems)
        XCTAssertEqual(secondStore.load(), secondItems)
        XCTAssertEqual(try Data(contentsOf: itemsFile(in: first)), firstBytes)
    }

    func testAwaitedAsyncSaveIsReadableByANewService() async throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)
        let item = ShelfItem(kind: .text(string: "async fixture"))

        await service.saveAsync([item])

        let raw = try XCTUnwrap(JSONSerialization.jsonObject(
            with: Data(contentsOf: itemsFile(in: directory))
        ) as? [[String: Any]])
        XCTAssertEqual(raw.first?["id"] as? String, item.id.uuidString)
        XCTAssertEqual(try ShelfPersistenceService(storageDirectory: directory).load(), [item])
    }

    func testLoadingMalformedFixtureNeverChangesItsOriginalBytes() throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)
        let bytes = Data("synthetic malformed JSON".utf8)
        try bytes.write(to: itemsFile(in: directory))

        XCTAssertTrue(service.load().isEmpty)

        XCTAssertEqual(try Data(contentsOf: itemsFile(in: directory)), bytes)
    }

    func testPartialDecodeReturnsValidItemsWithoutRewritingInput() throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)
        let id = try XCTUnwrap(UUID(uuidString: "00000000-0000-0000-0000-000000000001"))
        let valid = ShelfItem(id: id, kind: .text(string: "retained fixture"))
        let bytes = Data(
            """
            [
              {"id":"00000000-0000-0000-0000-000000000001",
               "kind":{"type":"text","value":"retained fixture"},"isTemporary":false},
              {"id":"invalid"}
            ]
            """.utf8
        )
        try bytes.write(to: itemsFile(in: directory))

        XCTAssertEqual(service.load(), [valid])

        XCTAssertEqual(try Data(contentsOf: itemsFile(in: directory)), bytes)
    }

    func testDirectoryCreationFailurePreservesTheOccupiedFixturePath() throws {
        let directory = try directory()
        let occupied = directory.appendingPathComponent("occupied")
        let bytes = Data("do not replace".utf8)
        try bytes.write(to: occupied)

        XCTAssertThrowsError(try ShelfPersistenceService(storageDirectory: occupied))

        XCTAssertEqual(try Data(contentsOf: occupied), bytes)
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: directory.path), ["occupied"])
    }

    func testSaveWithReplacedParentPreservesRetainedIndexAndObstruction() throws {
        let root = try directory()
        let storage = root.appendingPathComponent("storage", isDirectory: true)
        let retained = root.appendingPathComponent("retained", isDirectory: true)
        let service = try ShelfPersistenceService(storageDirectory: storage)
        service.save([ShelfItem(kind: .text(string: "original fixture"))])
        let original = try Data(contentsOf: itemsFile(in: storage))
        try FileManager.default.moveItem(at: storage, to: retained)
        let obstruction = Data("parent replaced; do not overwrite".utf8)
        try obstruction.write(to: storage)

        service.save([ShelfItem(kind: .text(string: "must not persist"))])

        XCTAssertEqual(try Data(contentsOf: itemsFile(in: retained)), original)
        XCTAssertEqual(try Data(contentsOf: storage), obstruction)
        XCTAssertEqual(Set(try FileManager.default.contentsOfDirectory(atPath: root.path)), ["storage", "retained"])
    }

    func testNonFileStorageURLIsRejectedBeforeFilesystemAccess() throws {
        let url = try XCTUnwrap(URL(string: "https://example.invalid/fixture"))

        XCTAssertThrowsError(try ShelfPersistenceService(storageDirectory: url)) { error in
            XCTAssertEqual((error as? CocoaError)?.code, .fileWriteUnsupportedScheme)
        }
    }

    func testEmptySaveReplacesOnlyTheFixtureIndex() throws {
        let directory = try directory()
        let service = try ShelfPersistenceService(storageDirectory: directory)
        service.save([ShelfItem(kind: .text(string: "temporary list"))])
        let sentinel = directory.appendingPathComponent("sentinel.txt")
        try Data("preserve unrelated fixture content".utf8).write(to: sentinel)

        service.save([])

        let raw = try XCTUnwrap(JSONSerialization.jsonObject(
            with: Data(contentsOf: itemsFile(in: directory))
        ) as? [Any])
        XCTAssertTrue(raw.isEmpty)
        XCTAssertTrue(service.load().isEmpty)
        XCTAssertEqual(try String(contentsOf: sentinel, encoding: .utf8), "preserve unrelated fixture content")
    }
}
