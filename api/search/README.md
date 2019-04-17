## Structured Search

The purpose of this submodule is to provide a structured query language for advanced
querying of the Elastic Search database. This advanced query language allows for
more control over how search results are matched and returned, with a variety of
comparison operators that can be combined with boolean logic.

### Examples

Search for files that match specific anatomy:
```
file.info.Anatomy IN [Brain, Neck]
```

Search for a specific series:
```
acquisition.label = FLAIR AND subject.label IN [baseline, week-32]
```

Wildcard search for patients by id:
```
subject.code LIKE "patient 100?"
```

Find any subject where the species is not set:
```
NOT subject.species EXISTS
```

### Keywords

Keywords can either be all uppercase or all lowercase, but not mixed case.
The following are keywords in the structured query language: `AND, OR, NOT, IN, LIKE, CONTAINS, EXISTS`
And the lowercase alternatives: `and, or, not, in, like, contains, exists`

### Comparison Operators

The following comparison operators are available:

- **=, ==** - Equals, compares terms for an exact match
- **!=, <>** - Not Equals, matches any document where the term is NOT an exact match
- **<** - Less than, matches any document where the term is less than the specified value
- **<=** - Less than or equal to, matches any document where the term is less than or equal to the specified value
- **>** - Greater than, matches any document where the term is greater than the specified value
- **>=** - Greater than or equal to, matches any document where the term is greater than or equal to the specified value
- **=~** - Regular expression match against the term
- **!~** - Negated regular expression match against the term
- **IN** - Returns any document where the term matches any value in the provided list
- **LIKE** - Uses wildcard matching against a term. Permitted wildcards are: `_`, `?` (Single character) and `%`, `*` (Multiple characters)
- **CONTAINS** - Compares analyzed field against the analyzed field and returns any documents that match
- **EXISTS** - Returns any document where the field is not null or empty

### Boolean Operators

Queries can be combined with a combination of grouping using parentheses, NOT, AND, and OR.
If no grouping is used, then OR takes precedence over AND in the parser.

### Type Comparisons

The following type conversions happen when converting to an elastic query:

- **boolean** - The literal values `true` and `false` will be converted to booleans.
- **integer** - Positive and negative integers will be converted to ints.
- **decimal** - Decimal numbers will be converted to floats - scientific notation not supported.
- **date** - Date strings in the form of `YYYY-MM-DD` are accepted and will be converted automatically.
- **timestamp** - Date/Time strings in ISO-8601 format will be converted automatically. Subsecond resolution and timezone offset are permitted but optional.

### Modules
The following submodules are present in this module:

- **ast** - Classes for representing the Syntax Tree
- **elastic** - Provides functions to convert from Syntax Tree to Elastic Query documents
- **partial_parser** - Provides support for generating suggestions for a query string
- **query_lexer** - Implementation of tokenizer for flyql using PLY's lexer
- **query_parser** - Implementation of a parser for flyql using PLY's YACC

### BNF

The following is a rough BNF description of the query language. See `query_lexer.py` and `query_parser.py` for 
the actual definition and implementation.
```
<expression> := <binary_expression> | <unary_expression>

<binary_expression> := <expression> <and> <expression>
                     | <expression> <or> <expression>

<unary_expression> := <not> <expression>
                    | ( <expression> )
                    | <term>

<term> := <comparison_term> | <in_term> | <exists_term>

<comparison_term> := <field> <operator> <phrase>

<in_term> := <field> <in> [ <phrase_list> ]

<exists_term> := <field> <exists>

<phrase_list> := <phrase>
               | <phrase_list> , <phrase>

<field> := <id> | <quoted_string>

<phrase> := <id> | <quoted_string>

<id> := /[^\'"\[\]\(\),\s]+/

<quoted_string> := /"([^"\]|(\\\"))*"/

<operator> := = | == | != | <> | < | <= | > | >= | =~ | !~ | CONTAINS | contains | LIKE | like

<and> := AND | and

<or> := OR | or

<not> := NOT | not

<in> := IN | in

<exists> := EXISTS | exists
```

### References

- [Elastic Structured Search](https://www.elastic.co/guide/en/elasticsearch/guide/current/structured-search.html)
- [PLY (Python Lex-Yacc)](https://www.dabeaz.com/ply/ply.html)
- [Parsing with PLY](http://www.dalkescientific.com/writings/NBN/parsing_with_ply.html)
