# CSV exports and spreadsheet safety

Agentopsy escapes spreadsheet-sensitive **text when exporting**, following
[OWASP CSV injection guidance](https://community.owasp.org/attacks/CSV_Injection).
The SQLite records, JSON APIs, CSV column names/order, and numeric values are unchanged.

Every field is quoted by Python's CSV writer; embedded double quotes are doubled.
Commas, semicolons, and line breaks remain inside their original fields. Quoting
alone does not stop formulas, so risky text also receives a leading apostrophe.

The export checks an NFKC-normalized inspection copy for `=`, `+`, `-`, `@` and
compatibility forms such as fullwidth operators. It conservatively protects leading
whitespace, Unicode separators, controls, format characters (including zero-width
and bidirectional controls), combining marks, and minus/plus lookalikes. It keeps
the original text after the prefix; normalization never rewrites stored or exported
content. Actual numeric values, including negative numbers, receive no prefix.
A label containing the string `-42` is untrusted text and is protected as text.

## Excel and LibreOffice limitations

CSV has no enforceable cell types. Excel and LibreOffice versions, locales, and
import settings can interpret apostrophes differently; the prefix may be visible.
These exports prioritize safe spreadsheet viewing over byte-identical text round
trips. Programmatic consumers can use the unchanged JSON APIs for original values.

OWASP warns that Excel can discard escapes when a CSV is saved and reopened.
It also describes an Excel-specific tab prefix, whose behavior differs across
spreadsheet applications. Agentopsy uses the apostrophe text convention with
correct quoting; it does not claim a universal or re-save-proof CSV defense.
Use the spreadsheet's text/CSV import dialog, explicitly import untrusted text
columns as **Text**, and disable formula evaluation where available. Do not remove
the prefix or assume a re-saved CSV retains these protections. For repeated editing,
save the imported sheet in a native workbook format while retaining text cell types.
Do not enable external links, macros, or other active content from an untrusted file.

Automated tests use inert arithmetic strings and verify exported bytes, CSV parsing,
numeric preservation, unchanged database/API values, and public read-only boundaries.
They do not execute formulas or certify every Excel/LibreOffice release or locale.
The public demo continues to reject uploads and mutations and use read-only SQLite;
CSV protection applies to its exports too, with attribution and notices retained.
