"""Tests for src/sange/core/enhancer/templates.py — registry + composition."""

from __future__ import annotations

import pytest

from sange.core.enhancer.templates import (
    PromptTemplate,
    RenderedPrompt,
    TemplateConflictError,
    TemplateCycleError,
    TemplateMissingVariableError,
    TemplateNotFoundError,
    TemplateRegistry,
)

# --------------------------------------------------------------------------- #
# PromptTemplate validators
# --------------------------------------------------------------------------- #


class TestPromptTemplateConstruction:
    def test_minimal(self) -> None:
        t = PromptTemplate(
            id="hello",
            version="1.0.0",
            task="greeting",
            user_template="Say hi to {name}",
            required_vars=("name",),
        )
        assert t.id == "hello"
        assert t.key == ("hello", "1.0.0")
        assert t.system_template == ""
        assert t.includes() == frozenset()

    def test_includes_extracted(self) -> None:
        t = PromptTemplate(
            id="parent",
            version="1.0.0",
            task="greeting",
            user_template="{{include:greeting}} and {{include:closing}}",
        )
        assert t.includes() == frozenset({"greeting", "closing"})

    @pytest.mark.parametrize("bad_id", ["Foo", "1abc", "has space", "has_under", ""])
    def test_id_must_be_kebab_case(self, bad_id: str) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            PromptTemplate(
                id=bad_id, version="1.0.0", task="t", user_template="x"
            )

    def test_empty_version_rejected(self) -> None:
        with pytest.raises(ValueError, match="version"):
            PromptTemplate(id="t", version="", task="t", user_template="x")

    def test_empty_task_rejected(self) -> None:
        with pytest.raises(ValueError, match="task"):
            PromptTemplate(id="t", version="1.0", task="", user_template="x")

    def test_empty_user_template_rejected(self) -> None:
        with pytest.raises(ValueError, match="user_template"):
            PromptTemplate(id="t", version="1.0", task="t", user_template="")

    def test_required_var_must_be_referenced(self) -> None:
        with pytest.raises(ValueError, match="never referenced"):
            PromptTemplate(
                id="t",
                version="1.0",
                task="t",
                user_template="static content",
                required_vars=("missing_var",),
            )

    def test_required_var_in_system_template_ok(self) -> None:
        # Variable can be referenced in system OR user template.
        t = PromptTemplate(
            id="t",
            version="1.0",
            task="t",
            system_template="Hello {who}",
            user_template="static",
            required_vars=("who",),
        )
        assert "who" in t.required_vars


# --------------------------------------------------------------------------- #
# TemplateRegistry — register/get/has
# --------------------------------------------------------------------------- #


def _tpl(id_: str = "t", v: str = "1.0.0", user: str = "Hello {name}",
         req: tuple[str, ...] = ("name",)) -> PromptTemplate:
    return PromptTemplate(
        id=id_, version=v, task="t", user_template=user, required_vars=req
    )


class TestTemplateRegistry:
    def test_register_and_get(self) -> None:
        t = _tpl()
        reg = TemplateRegistry([t])
        assert reg.get("t") is t
        assert reg.get("t", "1.0.0") is t

    def test_conflict_rejected(self) -> None:
        reg = TemplateRegistry([_tpl()])
        with pytest.raises(TemplateConflictError):
            reg.register(_tpl())

    def test_not_found(self) -> None:
        reg = TemplateRegistry()
        with pytest.raises(TemplateNotFoundError):
            reg.get("nope")

    def test_not_found_version(self) -> None:
        reg = TemplateRegistry([_tpl(v="1.0.0")])
        with pytest.raises(TemplateNotFoundError):
            reg.get("t", "9.9.9")

    def test_has(self) -> None:
        reg = TemplateRegistry([_tpl()])
        assert reg.has("t")
        assert reg.has("t", "1.0.0")
        assert not reg.has("t", "9.9.9")
        assert not reg.has("nope")

    def test_ids(self) -> None:
        reg = TemplateRegistry([_tpl(id_="b"), _tpl(id_="a")])
        assert reg.ids() == ("a", "b")  # sorted


# --------------------------------------------------------------------------- #
# Rendering — variables + includes + cycles
# --------------------------------------------------------------------------- #


class TestRendering:
    def test_basic_render(self) -> None:
        reg = TemplateRegistry([_tpl()])
        rendered = reg.render("t", {"name": "world"})
        assert isinstance(rendered, RenderedPrompt)
        assert rendered.user == "Hello world"
        assert rendered.system == ""
        assert rendered.template_id == "t"
        assert rendered.template_version == "1.0.0"

    def test_render_missing_var(self) -> None:
        reg = TemplateRegistry([_tpl()])
        with pytest.raises(TemplateMissingVariableError, match="name"):
            reg.render("t", {})

    def test_render_with_system(self) -> None:
        t = PromptTemplate(
            id="x", version="1.0", task="t",
            system_template="You are {persona}",
            user_template="Hi {name}",
            required_vars=("persona", "name"),
        )
        reg = TemplateRegistry([t])
        out = reg.render("x", {"persona": "helpful", "name": "world"})
        assert out.system == "You are helpful"
        assert out.user == "Hi world"

    def test_unknown_variable_left_in_text(self) -> None:
        # We use _safe_format that leaves unknown {var} as-is.
        t = PromptTemplate(
            id="x", version="1.0", task="t",
            user_template="Hi {name} and {unknown_var}",
            required_vars=("name",),
        )
        reg = TemplateRegistry([t])
        out = reg.render("x", {"name": "world"})
        # `unknown_var` isn't required so it survives literally.
        assert "{unknown_var}" in out.user

    def test_include_resolves(self) -> None:
        inner = PromptTemplate(
            id="greeting", version="1.0", task="t",
            user_template="Hello {name}",
            required_vars=("name",),
        )
        outer = PromptTemplate(
            id="parent", version="1.0", task="t",
            user_template="{{include:greeting}}! Welcome.",
            required_vars=("name",),
        )
        reg = TemplateRegistry([inner, outer])
        out = reg.render("parent", {"name": "world"})
        assert out.user == "Hello world! Welcome."

    def test_include_missing(self) -> None:
        t = PromptTemplate(
            id="x", version="1.0", task="t",
            user_template="{{include:nope}}",
        )
        reg = TemplateRegistry([t])
        with pytest.raises(TemplateNotFoundError):
            reg.render("x", {})

    def test_include_cycle(self) -> None:
        a = PromptTemplate(
            id="a", version="1.0", task="t", user_template="{{include:b}}"
        )
        b = PromptTemplate(
            id="b", version="1.0", task="t", user_template="{{include:a}}"
        )
        reg = TemplateRegistry([a, b])
        with pytest.raises(TemplateCycleError, match="cycle"):
            reg.render("a", {})

    def test_include_self_cycle(self) -> None:
        t = PromptTemplate(
            id="x", version="1.0", task="t", user_template="{{include:x}}"
        )
        reg = TemplateRegistry([t])
        with pytest.raises(TemplateCycleError):
            reg.render("x", {})

    def test_render_propagates_schema(self) -> None:
        t = PromptTemplate(
            id="x", version="1.0", task="t",
            user_template="Foo {name}",
            required_vars=("name",),
            output_schema={"type": "object", "required": ["foo"]},
        )
        reg = TemplateRegistry([t])
        out = reg.render("x", {"name": "world"})
        assert out.output_schema == {"type": "object", "required": ["foo"]}


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #


class TestEdgeCases:
    def test_empty_registry_ids(self) -> None:
        assert TemplateRegistry().ids() == ()

    def test_double_brace_escape_not_treated_as_var(self) -> None:
        # `{{x}}` (without `include:` prefix) is the str.format escape
        # for a literal `{x}`. Our _VAR_PATTERN uses a negative
        # lookbehind to skip these.
        t = PromptTemplate(
            id="x", version="1.0", task="t",
            user_template="Use {{x}} verbatim and {name}",
            required_vars=("name",),
        )
        reg = TemplateRegistry([t])
        out = reg.render("x", {"name": "world"})
        assert "{x}" in out.user
        assert "world" in out.user
