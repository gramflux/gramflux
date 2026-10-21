"""Detailed, source-checked reference rendering with curated developer contracts."""

import html
import inspect
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from gramflux import Client, buttons, events, filters
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.methods import method_name
from gramflux.tl.model import python_name

DATA = Path(__file__).with_name("data")

RAW_NOTES = {
    "peer": (
        "Native target peer. Unlike high-level Client methods, this argument does not "
        "accept a username or the string 'me'; resolve it first or construct "
        "InputPeerSelf."
    ),
    "channel": (
        "Native input channel identifying the channel/supergroup and its access "
        "information. An InputPeerChannel and an InputChannel are different TL result "
        "types; use the constructor required below."
    ),
    "bot": (
        "Native bot input user. Resolve the account and use the appropriate InputUser "
        "variant, not an untyped username or bot token."
    ),
    "user_id": (
        "User identity/reference in this endpoint's exact TL form. A numeric user ID is "
        "not interchangeable with InputUser; inspect the declared type and constructor "
        "choices below."
    ),
    "id": (
        "Resource identifier/reference scoped to this endpoint. The declared TL type "
        "determines whether it is an integer, string, native object or collection. Do not"
        " substitute another API's ID format."
    ),
    "hash": (
        "Method-specific resource/authorization hash or cache fingerprint. Zero is only "
        "meaningful where the endpoint explicitly defines cache bypass; never replace a "
        "required authorization/access hash with a guessed zero."
    ),
    "access_hash": (
        "Server-issued access hash paired with the corresponding resource identity. "
        "Obtain it from real account-visible metadata; it is not derivable from a numeric"
        " ID."
    ),
    "limit": (
        "Maximum number of entries requested in this one server response. This raw limit "
        "is not GramFlux's high-level cross-page total, and the server may return fewer "
        "items."
    ),
    "offset": (
        "Pagination cursor/offset in the exact type declared here. Numeric offsets and "
        "opaque string cursors are different protocols; use the previous result's cursor "
        "when defined by the endpoint."
    ),
    "offset_id": (
        "Message/resource ID cursor for this endpoint's pagination. It is not a Python "
        "list index. Combine with offset_date/add_offset only as defined by the endpoint."
    ),
    "offset_date": (
        "Unix-second date cursor, not a datetime object or millisecond timestamp. The raw"
        " serializer performs no implicit timezone or date conversion."
    ),
    "add_offset": (
        "Signed additional pagination displacement relative to the other cursor fields. "
        "This is distinct from offset_id and does not set a result limit."
    ),
    "min_id": (
        "Lower ID bound in this endpoint's result-selection protocol. It is independent "
        "of the peer identity and the number of requested rows."
    ),
    "max_id": (
        "Upper message/resource bound or read cursor as specified by the endpoint. Do not"
        " assume that the same zero sentinel has identical semantics in every method."
    ),
    "random_id": (
        "Client-generated signed-64-bit random identifier used by the method's "
        "deduplication/mapping protocol. Generate it securely and retain it when "
        "reconciling one logical operation; do not blindly create a new identity after a "
        "lost write reply."
    ),
    "msg_id": (
        "Message ID scoped to the selected peer or service-message context. It is "
        "distinct from query_id and the MTProto transport message ID."
    ),
    "message": (
        "Literal message-body string. GramFlux does not apply a Markdown/HTML parser to "
        "raw fields. Explicit entities use Telegram UTF-16 offsets."
    ),
    "entities": (
        "Native MessageEntity collection describing formatting in UTF-16 code units. "
        "Supply an explicit empty list to encode an empty vector; None omits an optional "
        "vector."
    ),
    "reply_markup": (
        "Native reply/inline keyboard markup. Use the exact permitted ReplyMarkup "
        "variant; None means the optional field is absent, not a universal remove-markup "
        "instruction."
    ),
    "reply_to": (
        "Native reply relationship object. Raw InputReplyTo is not interchangeable with "
        "the high-level integer reply_to convenience parameter."
    ),
    "silent": (
        "Request silent delivery where supported by this operation. This affects "
        "notification behavior, not account visibility or message permissions."
    ),
    "no_webpage": (
        "Flag selecting suppression of webpage previews. It is the inverse of the "
        "high-level link_preview option."
    ),
    "query": (
        "Endpoint-specific query payload. A generic !X query must be a native request "
        "object, not the result of awaiting client.api; other query types follow the "
        "declared TL shape."
    ),
    "query_id": (
        "Server-issued callback, inline-query or service query identity. Use the "
        "identifier from the corresponding object/event rather than a message ID."
    ),
    "phone_number": (
        "Account/contact phone string in the format expected by Telegram. It is "
        "sensitive; do not log request values."
    ),
    "phone_code_hash": (
        "Server-issued hash from auth.sendCode/resendCode. Pair it with the same "
        "account/session challenge; it is not the numeric login code."
    ),
    "phone_code": (
        "User-provided login code for the current challenge. Never persist it in a "
        "session snapshot or routine log."
    ),
    "password": (
        "Native password/SRP-related object required by this endpoint. Raw password "
        "fields are not automatically converted from a plain password string; use the "
        "high-level password workflow when available."
    ),
    "api_id": "Numeric application registration ID. It is not a Telegram user or bot ID.",
    "api_hash": (
        "Sensitive application API hash. The raw serializer does not retrieve it from "
        "Client settings when it is an explicit field."
    ),
    "lang_code": (
        "Endpoint-specific language code; an empty string sentinel is valid only where "
        "documented by that endpoint. No translation is performed by GramFlux."
    ),
    "file": (
        "Native file/media input reference required by this endpoint. A local path is not"
        " uploaded automatically by a raw method."
    ),
    "bytes": (
        "Binary chunk/payload bytes. This is not a path, base64 text or a request to read"
        " an entire file automatically."
    ),
    "file_part": (
        "Zero-based upload-part index for this file's part protocol. Track indices "
        "alongside the same file_id."
    ),
    "file_total_parts": (
        "Total number of parts in the big-file upload protocol; this must agree across "
        "the upload, not merely the current batch size."
    ),
    "cache_time": (
        "Requested server/client cache lifetime in seconds for the response. It is "
        "independent from GramFlux's local peer-cache capacity."
    ),
    "schedule_date": (
        "Scheduled-send Unix-second timestamp where permitted. Raw method exposure does "
        "not implement an application scheduler or a persistence queue."
    ),
    "send_as": (
        "Native peer to use as the sending identity, subject to Telegram permissions. "
        "This is separate from the destination peer."
    ),
    "data": (
        "Endpoint-specific binary or string payload as declared below. Callback payloads,"
        " encrypted input and opaque service data are not interchangeable."
    ),
    "media": (
        "Native input-media variant. Each variant has its own required fields; creating a"
        " declaration does not complete upload, payment or cross-DC authorization "
        "workflows."
    ),
    "top_msg_id": (
        "Root/top message ID selecting the topic/thread context supported by this method."
        " It is not an arbitrary current message ID."
    ),
    "revoke": (
        "Explicit server-side revocation/deletion flag. Assess the endpoint's scope and "
        "permissions before using it; a raw call bypasses high-level chat-scope preflight"
        " checks."
    ),
}

TYPE_NOTES = {
    "int": (
        "Python int encoded as a signed 32-bit little-endian value. Booleans are not "
        "accepted as integers; overflow is rejected. Endpoint-specific allowed "
        "ranges/sentinels still apply."
    ),
    "long": (
        "Python int encoded as a signed 64-bit little-endian value. Do not use float for "
        "large IDs or convert an opaque hash into a guessed ID."
    ),
    "double": (
        "Finite Python int/float encoded as an IEEE-754 double. NaN and infinity are "
        "rejected; coordinate/range semantics belong to the endpoint."
    ),
    "string": (
        "Python str encoded as a TL UTF-8 string. No implicit parsing, username "
        "resolution, timestamp conversion or URL fetching occurs."
    ),
    "bytes": (
        "Python bytes encoded as a TL byte string. A Python str, local filename or base64"
        " representation is not accepted in place of the bytes."
    ),
    "int128": (
        "Exactly 16 bytes. This is the wire-sized binary value, not a Python integer or "
        "hexadecimal text."
    ),
    "int256": (
        "Exactly 32 bytes. This is the wire-sized binary value, not a Python integer or "
        "hexadecimal text."
    ),
    "Bool": (
        "Python bool serialized with Telegram's boxed Bool constructor. This is different"
        " from a flag-only true field."
    ),
    "true": (
        "Flag-only boolean. False leaves its bit unset; True sets the bit. No separate "
        "boolean constructor is serialized for this field."
    ),
}


def load_content() -> dict[str, Any]:
    result: dict[str, Any] = json.loads((DATA / "client_reference.json").read_text())
    return result


def default(parameter: inspect.Parameter) -> str:
    if parameter.default is inspect.Parameter.empty:
        return "Required"
    if isinstance(parameter.default, filters.Filter):
        return "filters.all_messages"
    return repr(parameter.default)


def parameter_table(name: str, function: Any, content: dict[str, Any]) -> list[str]:
    from .docs import table_type

    result = [
        "## Parameters",
        "",
        "| Parameter | Python type | Default | Passing |",
        "| --- | --- | --- | --- |",
    ]
    parameters = [
        p
        for p in inspect.signature(function).parameters.values()
        if p.name not in {"self", "cls"} and not p.name.startswith("_")
    ]
    if not parameters:
        return ["## Parameters", "", "This method accepts no public arguments.", ""]
    for parameter in parameters:
        passing = (
            "Keyword-only" if parameter.kind == parameter.KEYWORD_ONLY else "Positional or keyword"
        )
        if parameter.kind == parameter.VAR_POSITIONAL:
            passing = "Variadic positional"
        result.append(
            f"| `{parameter.name}` | `{table_type(parameter.annotation)}` | "
            f"`{default(parameter)}` | {passing} |"
        )
    result += [""]
    for parameter in parameters:
        meaning = content["overrides"].get(
            name + "." + parameter.name, content["parameters"].get(parameter.name)
        )
        if not meaning:
            raise ValueError(f"missing parameter explanation: {name}.{parameter.name}")
        result += [f"### {parameter.name}", "", meaning, ""]
        if parameter.default is None:
            result += [
                (
                    "**Omission:** the Python default is None. It is not automatically "
                    "equivalent to an empty string, zero, False or an empty collection. "
                    "The behavior above defines this method's interpretation."
                ),
                "",
            ]
    return result


def native_variants(kind: str) -> list[type[Any]]:
    return [
        cls
        for cls in REGISTRY.values()
        if not cls.definition.method
        and cls.definition.result == kind
        and cls.definition.name != "vector"
    ]


def type_details(kind: str) -> list[str]:
    value = kind.split("?", 1)[-1]
    if value.startswith(("Vector<", "vector<")):
        inner = value[value.index("<") + 1 : -1]
        return [
            (
                f"Use a Python list of `{inner}` values. The codec also accepts tuples; "
                f"the generated facade's annotation is list. An empty list encodes a "
                f"present empty vector. Each element must satisfy the element type."
            ),
            "",
        ] + type_details(inner)
    if value.startswith("!") or value in {"X", "Object"}:
        return [
            (
                "Use a native TL object. A generic !X wrapper query must contain a native"
                " method/request object. Construct the inner request with "
                "gramflux.raw.functions; do not await it first and pass its decoded "
                "result."
            ),
            "",
        ]
    if value in TYPE_NOTES:
        return [TYPE_NOTES[value], ""]
    choices = native_variants(value)
    if not choices:
        return [
            (
                f"This is the schema's named `{value}` result type. Use a native object "
                f"matching that TL result, not a dictionary or a foreign library object."
            ),
            "",
        ]
    lines = [
        f"Select a native `{value}` constructor. Available variants in the pinned schema:",
        "This is a type-compatibility list, not a promise that every variant is valid "
        "for this endpoint. Empty/self/resource variants still depend on the method "
        "and account context.",
        "",
        "| Native constructor | Required fields | Optional fields |",
        "| --- | --- | --- |",
    ]
    for cls in choices:
        d = cls.definition
        namespace, _, tail = d.name.rpartition(".")
        path = (
            "types."
            + (namespace + "." if namespace else "")
            + python_name(tail[:1].upper() + tail[1:])
        )
        required = [
            f"`{python_name(p.name)}: {p.type}`"
            for p in d.params
            if p.type != "#" and "?" not in p.type
        ]
        optional = [
            f"`{python_name(p.name)}: {p.type}`"
            for p in d.params
            if p.type != "#" and "?" in p.type
        ]
        lines.append(
            f"| `{path}` | {', '.join(required) or 'None'} | {', '.join(optional) or 'None'} |"
        )
    return lines + [
        "",
        (
            "Constructor fields are keyword-only. Flags words are calculated by the codec"
            " and must not be passed manually. Nested native objects must likewise match "
            "their declared result types."
        ),
        "",
    ]


def expand(output: dict[str, str]) -> dict[str, str]:
    from .docs import page, signature

    content = load_content()
    public = {
        name: fn
        for name, fn in inspect.getmembers(Client, inspect.isfunction)
        if not name.startswith("_")
    }
    if set(content["methods"]) != set(public) | {"__init__"}:
        raise ValueError("curated Client method documentation does not match the public surface")
    for name, function in {"__init__": Client, **public}.items():
        info = content["methods"][name]
        slug = "constructor" if name == "__init__" else name
        lines = page("Client." + (name if name != "__init__" else "constructor"), info["summary"])
        lines += [
            f"**Section:** {info['category']} · [Client index](../client.md)",
            "",
            info["summary"],
            "",
            "## Signature",
            "",
            "```python",
            (
                signature("Client", function).removesuffix(" -> None") + " -> Client"
                if name == "__init__"
                else signature(name, function)
            ),
            "```",
            "",
        ]
        lines += parameter_table(name, function, content)
        lines += [
            "## Returns",
            "",
            info["returns"],
            "",
            "## Example",
            "",
            (
                "Examples assume the imports below. Account operations require a "
                "connected, authorized client. Login methods instead operate on the "
                "connected pending-login session described in their constraints; "
                "construction and registration need no connection. Variables such as "
                "event, message_id, user_peer and location must come from real "
                "account-visible objects. Supply your own credentials and login inputs."
            ),
            "",
            "```python",
            "from gramflux import Client, Config, Session, buttons, events, filters",
            "from gramflux.raw import functions, types",
            "",
            info["example"],
            "```",
            "",
            "## Behavior and constraints",
            "",
        ]
        lines += ["- " + note for note in info["notes"]]
        lines += ["", "## Errors and recovery", ""]
        if name.startswith("on") or name.startswith("off") or name == "__init__":
            lines += [
                (
                    "This operation does not issue a Telegram RPC by itself. Invalid "
                    "configuration/registration can raise ConfigurationError or "
                    "TypeError. Callback execution errors are handled by the event "
                    "dispatcher, not by a synchronous registration return value."
                ),
                "",
            ]
        elif name == "disconnect":
            lines += [
                (
                    "Cleanup can surface storage/transport errors. Use an async context "
                    "or await disconnect in a finally block. Completion does not promise "
                    "cryptographic erasure of old SQLite pages or Python memory."
                ),
                "",
            ]
        else:
            lines += [
                (
                    "Invalid arguments may raise ConfigurationError, TypeError or "
                    "ValueError according to the validation boundary. Connected "
                    "operations can propagate LifecycleError, Telegram RPCError "
                    "subclasses (including FloodWait/MigrationRequired), TimeoutError and"
                    " asyncio.CancelledError. Inspect the operation-specific constraints "
                    "above; not every server error applies to every method."
                ),
                "",
                (
                    "A timeout/cancellation cannot retract an already accepted remote "
                    "mutation. GramFlux does not blindly replay writes after a lost "
                    "response. Preserve application state and reconcile before attempting"
                    " a mutation again."
                ),
                "",
            ]
            if name.startswith("iter_"):
                lines += [
                    (
                        "This is a lazy stream: validation/network failures may surface "
                        "while iterating, not when obtaining the iterator. Breaking "
                        "iteration does not prefetch the next page or undo earlier work."
                    ),
                    "",
                ]
            if info["category"] == "Files":
                lines += [
                    (
                        "Transfer size/chunk/window validation can raise ValueError or "
                        "FileTransferError; unsupported media/CDN/cross-DC pathways raise"
                        " explicit unsupported/transport errors. Progress-callback "
                        "failures propagate; caller-owned streams may keep partial data."
                    ),
                    "",
                ]
        lines += [
            (
                "[Error policy](../../guides/errors.md) · [Session "
                "rules](../../guides/sessions.md) · [Verification "
                "limits](../../design/compatibility.md)"
            ),
            "",
        ]
        output[f"client/{slug}.md"] = "\n".join(lines)
    # Preserve all old Client anchors/signatures while routing readers to complete pages.
    index = output["client.md"]
    for name in public:
        index = index.replace(
            f"### {name}\n",
            (
                f"### {name}\n\n{content['methods'][name]['summary']}\n\n[Full parameter "
                f"reference and examples](client/{name}.md)\n"
            ),
        )
    index = index.replace(
        "## Properties",
        "[Constructor parameters and examples](client/constructor.md)\n\n## Properties",
    )
    output["client.md"] = index

    source = json.loads((DATA / "official_reference.json").read_text())["methods"]
    for cls in REGISTRY.values():
        d = cls.definition
        if not d.method:
            continue
        namespace = d.name.rpartition(".")[0] or "root"
        method = method_name(d.name.rsplit(".", 1)[-1])
        path = "client.api." + (namespace + "." if namespace != "root" else "") + method
        facts = source.get(d.name, {})
        lines = page(
            d.name,
            f"Detailed {path} parameters, native object alternatives, flags, errors and results.",
        )
        lines += [
            (
                f"[Namespace index](../{namespace}.md) · [Raw API "
                f"conventions](../../../guides/async-api.md)"
            ),
            "",
            "## Purpose",
            "",
        ]
        if facts.get("summary_quote"):
            lines += [
                "> " + html.escape(facts["summary_quote"], quote=False),
                "",
                f"— [Telegram method reference]({facts['url']}) (short source excerpt).",
                "",
            ]
        eligibility = " ".join(facts.get("eligibility", [])).lower()
        if "both users and bots" in eligibility:
            lines += ["**Account eligibility:** user accounts and bot authorizations.", ""]
        elif "only users" in eligibility:
            lines += [
                "**Account eligibility:** user accounts only according to the official reference.",
                "",
            ]
        elif "only bots" in eligibility:
            lines += [
                "**Account eligibility:** bot authorizations only.",
                "",
            ]
        lines += [
            f"**Python call:** `{path}`",
            "",
            f"**Pinned constructor ID:** `0x{d.id:08x}` · **TL result:** `{d.result}`",
            "",
            (
                "This page documents the raw method, not a high-level Client shortcut. No"
                " username resolution, implicit upload, formatting parser or "
                "method-specific workflow is added by the facade."
            ),
            "",
            "## All supported parameters",
            "",
            "| Python keyword | Exact TL field | Default |",
            "| --- | --- | --- |",
        ]
        params = [p for p in d.params if p.type != "#"]
        for p in params:
            value = "False" if p.type.endswith("?true") else "None" if "?" in p.type else "Required"
            lines += [f"| `{python_name(p.name)}` | `{p.type}` | `{value}` |"]
        if not params:
            lines += ["| — | No parameters | — |"]
        lines += [""]
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for p in params:
            if "?" in p.type:
                flag = p.type.split("?", 1)[0]
                word, bit = flag.split(".")
                groups[(word, bit)].append(python_name(p.name))
            lines += [f"### {python_name(p.name)}", ""]
            if p.name in RAW_NOTES:
                lines += [RAW_NOTES[p.name], ""]
            quote = facts.get("parameter_notes", {}).get(p.name, "")
            if len(quote.removesuffix(" …").split()) >= 4:
                lines += [
                    "> " + html.escape(quote, quote=False),
                    "",
                    f"— [Telegram field note]({facts['url']}#parameters).",
                    "",
                ]
            if "?" in p.type:
                if p.type.endswith("?true"):
                    lines += [
                        (
                            f"**Presence:** flag-only boolean controlled by `{flag}`. "
                            f"Default False leaves this bit unset. True sets the bit; no "
                            f"boxed Bool value is transmitted."
                        ),
                        "",
                    ]
                else:
                    lines += [
                        (
                            f"**Presence:** optional value controlled by `{flag}`. None "
                            f"omits it. An empty string, zero or empty list remains a "
                            f"present encoded value; do not confuse omission with clearing."
                        ),
                        "",
                    ]
            else:
                lines += [
                    (
                        "**Presence:** required. The facade supplies no invented default;"
                        " omitting this keyword raises TypeError before any RPC."
                    ),
                    "",
                ]
            lines += type_details(p.type)
        lines += [
            "## Flags and related fields",
            "",
            (
                "TL flag words declared with # are not public arguments. "
                "The codec derives bits from the"
                " actual optional values. Fields sharing a bit are one conditional group:"
                " populated values must agree on presence or serialization fails before a"
                " valid request can be sent."
            ),
            "",
        ]
        shared = [(word, bit, names) for (word, bit), names in groups.items() if len(names) > 1]
        if shared:
            lines += [
                f"- `{word}.{bit}` groups: " + ", ".join(f"`{n}`" for n in names)
                for word, bit, names in shared
            ] + [""]
        else:
            lines += [
                "This declaration does not group multiple public fields under the same flag bit.",
                "",
            ]
        lines += [
            "## Request construction example",
            "",
            (
                "This is an argument-explicit call template. Define the `*_value` "
                "variables from valid application/server data using the descriptions "
                "above. It deliberately does not fabricate access hashes, code "
                "challenges, payment consent, random identifiers or protocol state. "
                "Required fields must be supplied even when another library would invent "
                "defaults."
            ),
            "",
            "```python",
            f"result = await {path}(",
        ]
        for p in params:
            arg = python_name(p.name)
            value = (
                "False"
                if p.type.endswith("?true")
                else "None"
                if "?" in p.type
                else arg.rstrip("_") + "_value"
            )
            lines.append(f"    {arg}={value},")
        lines += [
            ")",
            "```",
            "",
            (
                "Optional fields above are omitted by default. To enable one, replace "
                "None/False with the required value and satisfy any shared-bit group. See"
                " the dedicated Client convenience method when you want peer resolution "
                "or a file pipeline."
            ),
            "",
            "## Result and interpretation",
            "",
            (
                f"The declared server result is `{d.result}`. The native codec decodes the "
                f"actual constructor returned by Telegram; do not assume a Message simply "
                f"because the operation concerns messages."
            ),
            "",
        ]
        result_type = (
            d.result[d.result.index("<") + 1 : -1]
            if d.result.startswith(("Vector<", "vector<"))
            else d.result
        )
        if d.result.startswith(("Vector<", "vector<")):
            lines += [
                (
                    f"The result is a Python list of `{result_type}` values, not an async "
                    f"iterator or an auto-paginating collection."
                ),
                "",
            ]
        choices = native_variants(result_type)
        if choices:
            lines += (
                ["Possible native result constructors in the pinned schema:", ""]
                + ["- `" + c.__name__ + "`" for c in choices]
                + [""]
            )
        elif result_type in TYPE_NOTES:
            lines += [TYPE_NOTES[result_type], ""]
        lines += [
            "## Server errors and recovery",
            "",
            (
                "These are error identifiers documented on Telegram's method page, not an"
                " exhaustive compatibility promise or an automatically retried error "
                "list. RPC errors expose sanitized code/name; unknown identifiers remain "
                "RPCError."
            ),
            "",
        ]
        errors = facts.get("errors", [])
        if errors:
            lines += (
                ["| RPC code | Server error name/pattern |", "| --- | --- |"]
                + [f"| {e['code']} | `{e['name']}` |" for e in errors]
                + [""]
            )
        else:
            lines += [
                (
                    "No method-specific error table was published in the retained "
                    "official reference. Authentication, permission, rate-limit and "
                    "transport errors can still occur; an absent table is not proof of an"
                    " infallible operation."
                ),
                "",
            ]
        lines += [
            (
                "FloodWait requires an explicit bounded application waiting policy. "
                "Cancellation/timeouts do not retract accepted writes. MigrationRequired "
                "does not imply a general automatic DC switch/replay workflow. "
                "SerializationError/TypeError/overflow errors can reject malformed local "
                "values before a valid request reaches Telegram."
            ),
            "",
            "## Provenance and support boundary",
            "",
            (
                f"Official reference ID matches the pinned declaration: "
                f"**{facts.get('schema_id_matches', False)}**."
            ),
            "",
            (
                f"Reference retrieved: `{facts.get('retrieved_at', 'unavailable')}`. "
                f"Source SHA256: `{facts.get('sha256', 'unavailable')}`."
            ),
            "",
            (
                "The exact method ID and every argument above come from GramFlux's pinned"
                " schema. Short quotations and error identifiers come from the linked "
                "official page. A generated function does not by itself implement "
                "payments, secret chats, calls, CDN handling or other multi-step "
                "workflows. Consult the compatibility matrix before treating a raw entry "
                "point as a working high-level feature."
            ),
            "",
            (
                "[Compatibility](../../../design/compatibility.md) · [Error "
                "policy](../../../guides/errors.md)"
            ),
            "",
        ]
        output[f"raw/{namespace}/{method}.md"] = "\n".join(lines)
        ns_path = f"raw/{namespace}.md"
        output[ns_path] = output[ns_path].replace(
            f"## {method}\n",
            (
                f"## {method}\n\n[Detailed method page: every parameter, native variants, "
                f"flags and errors]({namespace}/{method}.md)\n"
            ),
        )
    from gramflux import Config, Session

    helper_modules = {"filters": filters, "buttons": buttons, "Session": Session}
    for qualified, info in content["helpers"].items():
        owner, name = qualified.split(".")
        function = getattr(helper_modules[owner], name)
        slug = qualified.replace(".", "-").lower()
        lines = page(qualified, info["summary"])
        lines += [
            info["summary"],
            "",
            "## Signature",
            "",
            "```python",
            signature(qualified, function),
            "```",
            "",
        ]
        lines += parameter_table(qualified, function, content)
        lines += [
            "## Returns",
            "",
            info["returns"],
            "",
            "## Example",
            "",
            "```python",
            "from gramflux import Client, Session, buttons, filters",
            "from gramflux.raw import types",
            "",
            info["example"],
            "```",
            "",
            "## Constraints and failure behavior",
            "",
            info["notes"],
            "",
            (
                "These examples assume a previously constructed client where one is used. "
                "Builders and selectors do not make a network request by themselves. Invalid "
                "builder/selector inputs raise ConfigurationError or the underlying Python "
                "argument/regex error. Session I/O errors arise when storage is actually "
                "opened during connect."
            ),
            "",
        ]
        output[f"helpers/{slug}.md"] = "\n".join(lines)
        parent = (
            "configuration.md"
            if owner == "Session"
            else "filters.md"
            if owner == "filters"
            else "buttons.md"
        )
        output[parent] += f"\n[{qualified}: complete parameter guide](helpers/{slug}.md)\n"

    event_examples = content["event_examples"]
    helper_meanings = {
        "MessageEvent.reply": (
            "Send literal text in reply to the bound message. Returns a native Message. "
            "The original message ID and peer are supplied by the event, while only the "
            "documented text/silent arguments can be changed."
        ),
        "MessageEvent.edit": (
            "Edit the bound message through Client.edit_message. Returns native Updates, "
            "not a refreshed Message. Account ownership/permissions apply; no formatting "
            "parser is added."
        ),
        "MessageEvent.delete": (
            "Delete the bound message through scoped Client.delete_messages. Returns the "
            "batch result list. Channel deletion requires explicit revoke=True, just as on"
            " Client."
        ),
        "MessageEvent.download": (
            "Download supported document/photo media from the bound message to the "
            "explicit destination. Returns the underlying Path/None contract. No automatic"
            " filename derived from untrusted media is selected."
        ),
        "CallbackQueryEvent.answer": (
            "Answer this callback's query_id through the bound Client. Returns Telegram's "
            "bool result. It does not edit the originating message or automatically "
            "acknowledge later queries."
        ),
        "InlineQueryEvent.answer": (
            "Answer this inline query with native results and explicit caching/pagination "
            "options. Returns Telegram's bool. Result validation and account eligibility "
            "follow Client.answer_inline_query."
        ),
    }
    property_meanings = {
        "text": (
            "Literal message text (or empty string for a service message). It may include "
            "private content and is not safe logging data by default."
        ),
        "outgoing": (
            "True when the bound message has its native out flag set. A false value is not"
            " a guarantee that a sender entity is available."
        ),
        "chat_id": content["event_fields"]["chat_id"],
        "sender_id": content["event_fields"]["sender_id"],
        "online": (
            "True exactly when status is the UserStatusOnline constructor. This property "
            "does not perform a fresh server request or create a separate clock-based "
            "presence guarantee."
        ),
        "action": (
            "Native MessageAction attached to the service message. Inspect its "
            "definition/constructor before accessing variant-specific fields."
        ),
        "user_ids": (
            "Tuple extracted for supported add-user/delete-user service actions. Other "
            "action kinds return an empty tuple; this is not a complete participant list."
        ),
    }
    from dataclasses import fields
    from typing import get_args

    from .docs import table_type

    for event_cls in get_args(events.Event):
        lines = page(
            event_cls.__name__,
            "Fields, native variants, helpers and delivery semantics for " + event_cls.__name__,
        )
        lines += [
            "[Event index](../events.md) · [Dispatcher behavior](../../guides/events.md)",
            "",
            "## Fields",
            "",
            "| Field | Python type | Meaning |",
            "| --- | --- | --- |",
        ]
        for field in fields(event_cls):
            meaning = content["event_fields"][field.name]
            lines.append(f"| `{field.name}` | `{table_type(field.type)}` | {meaning} |")
        lines += ["", "## Read-only properties", ""]
        properties = [
            (name, value)
            for name, value in inspect.getmembers(event_cls)
            if isinstance(value, property)
        ]
        if not properties:
            lines += ["This event exposes the fields above without extra derived properties.", ""]
        for name, _ in properties:
            lines += [f"### {name}", "", property_meanings[name], ""]
        for name, fn in inspect.getmembers(event_cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            qualified = event_cls.__name__ + "." + name
            lines += [
                f"## {name}",
                "",
                helper_meanings[qualified],
                "",
                "```python",
                signature(name, fn),
                "```",
                "",
            ]
            lines += parameter_table(qualified, fn, content)
        lines += [
            "## Example",
            "",
            "```python",
            "from gramflux import buttons, filters",
            "from gramflux.raw import types",
            "",
            event_examples[event_cls.__name__],
            "```",
            "",
            (
                "Register before connecting. Callbacks are awaited sequentially, errors are "
                "reported through the dispatcher, and shutdown cancellation does not commit an"
                " update merely because it was enqueued. Helpers require a bound "
                "client/context and raise LifecycleError for detached events; "
                "RPC/deadline/cancellation errors propagate normally."
            ),
            "",
            (
                "Raw field availability is not uniform across constructor variants. There is "
                "no exactly-once durable callback journal, and replays/duplicates across "
                "process failures remain possible. See the dispatcher and update-state guides "
                "for the complete commitment boundary."
            ),
            "",
        ]
        output[f"events/{event_cls.__name__}.md"] = "\n".join(lines)
        output["events.md"] = output["events.md"].replace(
            f"## {event_cls.__name__}\n",
            f"## {event_cls.__name__}\n\n"
            f"[Full field and helper reference](events/{event_cls.__name__}.md)\n",
        )
    output["configuration.md"] += "\n## Field behavior and validation\n\n"
    for field in fields(Config):
        output["configuration.md"] += (
            f"### {field.name}\n\n{content['config_fields'][field.name]}\n\n"
        )
    filter_meanings = {
        "all_messages": (
            "Always accepts the supplied event. The subscription chooses the event class; "
            "this predicate itself does not restrict delivery to messages."
        ),
        "text": (
            "Matches a nonempty text attribute. Whitespace counts as text. No entity "
            "parsing or event-class restriction is implied."
        ),
        "incoming": (
            "Matches events exposing outgoing=False. Events without this attribute do not match."
        ),
        "outgoing": (
            "Matches events whose outgoing attribute is truthy. Events without it do not match."
        ),
        "private": (
            "Matches chat_type equal to private using existing event data, without a "
            "network request."
        ),
        "group": (
            "Matches chat_type equal to group using existing event classification, without "
            "fetching participants."
        ),
        "channel": (
            "Matches chat_type equal to channel. This does not test the sender's identity "
            "or administrator permissions."
        ),
        "media": (
            "Matches the message's media classification without downloading or inspecting "
            "file contents."
        ),
        "photo": (
            "Matches the message's photo classification. An image filename on a document "
            "does not itself make this match."
        ),
        "document": (
            "Matches the message's document classification. Specific document attributes "
            "can also match video, audio, voice or sticker filters."
        ),
        "video": (
            "Matches the message's video classification derived from native document "
            "attributes, without downloading the file."
        ),
        "audio": (
            "Matches the message's audio classification derived from native document "
            "attributes. Use voice for voice-note classification."
        ),
        "voice": (
            "Matches the message's voice-note classification derived from native audio "
            "attributes, without decoding audio."
        ),
        "sticker": (
            "Matches the message's sticker classification derived from native document "
            "attributes, without fetching the sticker set."
        ),
    }
    for name, meaning in filter_meanings.items():
        output["filters.md"] = output["filters.md"].replace(
            f"`filters.{name}` is a composable synchronous predicate.",
            f"`filters.{name}` is a composable synchronous predicate.\n\n{meaning}",
        )
    output["filters.md"] += (
        "\n## Composition and evaluation\n\n"
        "Use `&` for AND, `|` for OR and `~` for NOT; parenthesize mixed operators. "
        "Predicates are synchronous and use existing event data without network I/O.\n\n"
        "```python\n"
        "selector = filters.incoming & filters.text & ~filters.command('start')\n"
        "```\n\n"
        "Subscriptions choose the event class. Filtering does not alter handler ordering "
        "or enable unsupported update processing.\n"
    )
    output["configuration.md"] = output["configuration.md"].rstrip() + "\n"
    return output
