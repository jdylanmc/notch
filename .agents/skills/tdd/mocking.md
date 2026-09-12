# When to Mock

Mock at **system boundaries** only:

- External APIs (payment, email, etc.)
- Databases (sometimes - prefer test DB)
- Time/randomness
- File system (sometimes)

Don't mock:

- Your own classes/modules
- Internal collaborators
- Anything you control

## Designing for Mockability

At system boundaries, design interfaces that are easy to mock:

**1. Use dependency injection**

Pass external dependencies in rather than creating them internally:

The Swift examples use hypothetical domain types. Replace them with the
repository's actual interfaces rather than adding a payment integration.

```swift
protocol PaymentClient {
    func charge(amount: Int) async throws -> PaymentReceipt
}

// Easy to mock
func processPayment(
    order: Order,
    client: any PaymentClient
) async throws -> PaymentReceipt {
    try await client.charge(amount: order.total)
}

// Hard to mock
func processPayment(order: Order) async throws -> PaymentReceipt {
    let client = LivePaymentClient()
    return try await client.charge(amount: order.total)
}
```

**2. Prefer SDK-style interfaces over generic fetchers**

Create specific functions for each external operation instead of one generic function with conditional logic:

```swift
import Foundation

// GOOD: Each function is independently mockable
protocol StoreClient {
    func user(id: UUID) async throws -> User
    func orders(userID: UUID) async throws -> [Order]
    func createOrder(_ draft: OrderDraft) async throws -> Order
}

// BAD: Mocking requires conditional logic inside the mock
protocol GenericTransport {
    func request(_ request: URLRequest) async throws -> Data
}
```

The SDK approach means:
- Each mock returns one specific shape
- No conditional logic in test setup
- Easier to see which endpoints a test exercises
- Type safety per endpoint

This is a preference for the domain-facing seam, not a prohibition on a shared
low-level transport behind it.
