---
name: codebase-design
description: Use when designing or improving a module's interface, finding deepening opportunities, placing seams, improving testability or AI-navigability, or when another skill needs deep-module vocabulary.
---

> Adaptation: Derived from mattpocock/skills; terminology and examples refined for this cross-host skill pack.

# Codebase Design

Design **deep modules**: much behaviour behind a small interface at a clean seam, testable through that interface. Aim for leverage for callers and locality for maintainers.

## Vocabulary

Use these terms consistently; do not substitute component/service/unit for module, API/signature for interface, or boundary for seam.

| Term | Meaning |
|---|---|
| **Module** | Anything with an interface and an implementation: function, class, package, or tier-spanning slice. Scale-agnostic. |
| **Interface** | Everything callers must know: types, invariants, ordering, errors, configuration, and performance characteristics. Broader than a TypeScript `interface` or public methods. Each module presents one interface to callers and tests. |
| **Implementation** | Code inside a module. Use this term for substance; use adapter when discussing its role at a seam. A small adapter may have a large implementation (Postgres repo), or vice versa (in-memory fake). |
| **Depth** | Behaviour callers/tests can exercise per unit of interface they learn. Deep: much behaviour behind a small interface. Shallow: interface nearly as complex as implementation. Measure leverage, not implementation/interface line counts, which reward padding. |
| **Seam** | Michael Feathers: a place where behaviour can change without editing in that place. The location of a module's interface; its placement is a separate design decision. Avoid boundary, overloaded with DDD bounded context. |
| **Adapter** | Concrete thing satisfying an interface at a seam. Describes role, not its contents. |
| **Leverage** | Capability callers get per unit of interface learned; one implementation serves N call sites and M tests. |
| **Locality** | Change, bugs, knowledge, and verification concentrate in one place rather than spreading across callers. |

## Principles and testability

- **Depth belongs to the interface.** Internals may be small, mockable, swappable parts, with private **internal seams** used by the module's tests. Keep these distinct from its **external seam**.
- **Deletion test:** if deleting a module makes complexity vanish, it was a pass-through. If complexity reappears across callers, it earned its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. Needing to test past it suggests the module has the wrong shape.
- **One adapter means a hypothetical seam; two means a real one.** Introduce a seam only when something actually varies across it.
- **Accept dependencies instead of creating them; return results instead of producing side effects.** For example, `processOrder(order, paymentGateway)` accepts its dependency; `calculateDiscount(cart): Discount` returns its result instead of mutating `cart.total`.
- **Shrink the surface:** fewer methods and simpler parameters reduce learning and test setup. Ask what complexity the implementation can hide.

## Further techniques

- For dependency categories, seam discipline, and replace-don't-layer testing, read [DEEPENING.md](DEEPENING.md).
- When exploring alternative interfaces, read [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md): parallel sub-agents design radically different interfaces, then compare depth, locality, and seam placement.
