# Good and Bad Tests

The snippets are XCTestCase methods using hypothetical commerce APIs, not
Notch Pocket features. Import XCTest and substitute the actual types and
interfaces under test; do not introduce these examples into the app.

## Good Tests

**Integration-style**: Test through real interfaces, not mocks of internal parts.

```swift
// GOOD: Tests observable behavior
func testCheckoutConfirmsValidCart() async throws {
    var cart = Cart()
    cart.add(Product(price: 15))
    let result = try await checkout(cart, paymentMethod: .card)
    XCTAssertEqual(result.status, .confirmed)
}
```

Characteristics:

- Tests behavior users/callers care about
- Uses public API only
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test

## Bad Tests

**Implementation-detail tests**: Coupled to internal structure.

```swift
// BAD: Tests implementation details
func testCheckoutCallsInternalPaymentService() async throws {
    let payment = PaymentSpy()
    let service = CheckoutService(paymentService: payment)
    let cart = Cart(items: [Product(price: 15)])
    _ = try await service.checkout(cart, paymentMethod: .card)
    XCTAssertEqual(payment.processedAmounts, [15])
}
```

Red flags:

- Mocking internal collaborators
- Testing private methods
- Asserting on call counts/order
- Test breaks when refactoring without behavior change
- Test name describes HOW not WHAT
- Verifying through external means instead of interface

```swift
// BAD: Bypasses interface to verify
func testCreateUserWritesDatabaseRow() throws {
    let database = UserDatabase.inMemory()
    let users = UserDirectory(database: database)
    _ = try users.createUser(name: "Alice")
    XCTAssertEqual(try database.countUsers(named: "Alice"), 1)
}

// GOOD: Verifies through interface
func testCreatedUserIsRetrievable() throws {
    let users = UserDirectory.inMemory()
    let created = try users.createUser(name: "Alice")
    let retrieved = try XCTUnwrap(users.user(id: created.id))
    XCTAssertEqual(retrieved.name, "Alice")
}
```

**Tautological tests**: Expected value restates the implementation, so the test passes by construction.

```swift
// BAD: Expected value is recomputed the way the code computes it
func testTotalRepeatsImplementation() {
    let items = [Product(price: 10), Product(price: 5)]
    let expected = items.reduce(0) { $0 + $1.price }
    XCTAssertEqual(calculateTotal(items), expected)
}

// GOOD: Expected value is an independent, known literal
func testTotalMatchesKnownAmount() {
    let items = [Product(price: 10), Product(price: 5)]
    XCTAssertEqual(calculateTotal(items), 15)
}
```
