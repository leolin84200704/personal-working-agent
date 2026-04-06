# MEMORY - Knowledge Index

> Agent's accumulated knowledge index. Every memory is learned from actual operations.

---

## Index

- [Repos](#repos) - Understanding of each repo's function and architecture
- [Patterns](#patterns) - Common modification patterns and practices
- [Gotchas](#gotchas) - Pitfalls and things to watch out for
- [Questions](#questions) - Questions asked and answers received
- [Jira](#jira) - Jira-related knowledge

---

## Repos

### LIS-transformer
- **Purpose**: HL7 transformation service, converts LIS format to HL7
- **Tech**: Python, Django
- **Key files**:
  - `src/hl7_parser.py` - HL7 parser
- **Notes**: ...

### LIS-transformer-v2
- **Purpose**: HL7 transformation v2
- **Status**: 🟝 To be explored

### EMR-Backend
- **Purpose**: EMR system backend
- **Tech**: Java, Spring Boot
- **Status**: 🟝 To be explored

---

## Patterns

### Adding Test Item Mapping
1. Modify corresponding mapping file
2. Update test data
3. Requires service restart

### HL7 Parser Modification
- Always add unit tests
- Watch for escape sequences in special character handling

---

## Gotchas

### Common Errors
- 🟝 To be filled (learned from actual operations)

---

## Questions

### Q: How to determine which repo to modify?
> **A**: First check ticket title keywords, then search relevant files in each repo

---

## Jira

### Project Keys
- LIS - LIS related projects
- EMR - EMR related projects

### Custom Fields
- `customfield_10000` - Sprint

---

*This file grows with every interaction. Last Updated: 2026-04-06*
