# ADR-005: tree-sitter for Java Source Code Parsing

## Status
Accepted

## Context

To extract domain knowledge from a Java codebase, we must first parse Java source files into a structured representation. The parser must:
- Handle all modern Java syntax (generics, lambdas, annotations, records)
- Extract class metadata: name, type (class/interface/enum), package, annotations, fields, methods, implemented interfaces, superclass
- Be executable from Python without requiring a JVM

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| `javalang` (Python library) | Unmaintained; fails on many modern Java constructs (records, sealed classes, text blocks) |
| ANTLR Java grammar | Requires generating a parser from a grammar; high setup complexity |
| JavaParser (Java library) | Requires running a JVM subprocess; cross-language communication overhead |
| Regex-based extraction | Cannot reliably parse nested generics, multi-line annotations, or complex method signatures |
| Calling the LLM to parse Java | Expensive, slow, and non-deterministic for a structural task |

## Decision

Use **tree-sitter** (`tree-sitter>=0.22.0`) with the **`tree-sitter-java`** grammar for all Java source file parsing.

tree-sitter is a fast, incremental, error-tolerant parser generator that:
- Has a mature Java grammar (`tree-sitter-java>=0.21.0`) covering all Java versions
- Provides Python bindings (`py-tree-sitter`) for direct use without subprocess calls
- Produces a concrete syntax tree (CST) that is traversed to extract `JavaClass` model objects
- Is error-tolerant — partial parse results are available even for files with syntax errors

The parsed output is normalised into typed Pydantic models (`JavaClass`, `JavaMethod`, `JavaField`, `JavaAnnotation`, `JavaParameter`) defined in [`src/models/java_models.py`](../../src/models/java_models.py). `JavaParameter` captures method parameter names, types, and any annotations (e.g., `@PathVariable`, `@RequestBody`).

Reference files:
- [`src/parsers/tree_sitter_parser.py`](../../src/parsers/tree_sitter_parser.py)
- [`src/analyzers/code_scanner.py`](../../src/analyzers/code_scanner.py)
- [`src/models/java_models.py`](../../src/models/java_models.py)

## Consequences

**Positive:**
- Handles all modern Java syntax reliably, including generics, annotations, lambdas, and records.
- No JVM dependency — runs entirely within the Python process.
- Fast: tree-sitter is implemented in C and can parse thousands of files per second.
- Error-tolerant: files with syntax errors produce partial results rather than hard failures; errors are captured in `parse_errors` state.
- Grammar is maintained by the tree-sitter community and updated alongside Java language evolution.

**Negative:**
- The tree-sitter Python API requires navigating a CST manually (no high-level AST API), making the parser code verbose and tied to the grammar's node type names.
- Grammar updates (`tree-sitter-java` version bumps) may change node names, requiring parser maintenance.
- Type resolution (e.g., resolving what `UserRepository` refers to) is not supported — tree-sitter only provides syntactic structure, not semantic analysis.
- The parser cannot resolve fully-qualified class names from import statements, limiting dependency analysis to simple name matching.
