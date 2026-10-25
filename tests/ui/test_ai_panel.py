# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del pannello dell'assistente (``mdfiles/44-ui-pannello-ia.md`` §12), sprint 7a e 7b.

pytest-qt sulla piattaforma ``offscreen``, provider simulato a copione del 35 (``ScriptedAdapter``: corpo JSON vero
del 30), Portachiavi simulato del 31 (``FakeKeychain``), nessuna rete e nessuna chiave reale. I numeri che il
"modello" scrive li copia il test dai risultati già mandati (regola d'oro n. 1).
"""

import json
import threading
import time

import pytest
from PySide6.QtCore import QElapsedTimer, QPoint, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QPushButton

from astrotwo.ai.provider_adapter import (
    PROVIDER_PRESETS,
    ProviderError,
    ProviderProfile,
    TextDelta,
    TurnEnd,
    make_adapter,
)
from astrotwo.ai.result_verification import CheckedNumber, VerificationReport, WrittenNumber
from astrotwo.ui.ai_panel import MARK_STATE_PROPERTY, CommandCard, ConfirmationCard, MessageView
from tests.ai.ai_workspace import INJECTION, INJECTION_ROWS, offline  # noqa: F401 - fixture
from tests.ai.fake_providers import (  # noqa: F401 - fixture provider_service
    FakeKeychain,
    Reply,
    ScriptedAdapter,
    calls_turn,
    numbers_sent,
    provider_service,
    text_turn,
    tool_call,
)
from tests.ai.test_provider_adapter import error_reply, text_reply, tools_reply
from tests.core.test_commands import region_command
from tests.core.test_commands_catalog_sky import write_catalog
from tests.ui.test_main_window import (  # noqa: F401 - fixture
    NIGHT_THRESHOLD,
    make_window,
    settings_path,
    stylesheet_colors,
    wait_idle,
)

REMOTE = "https://api.example.invalid/v1"
LOCAL = "http://127.0.0.1:11434/v1"
SECRET = "sk-finta-0123456789"
MODEL = "modello-finto"


def entry_for(url, model=MODEL, preset="custom"):
    return {"preset": preset, "kind": "openai_compatible", "base_url": url, "model": model,
            "max_output_tokens": 4096, "max_tokens_field": "max_tokens"}


def ai_window(qtbot, settings_path, cache, script=(), *, url=REMOTE, key=True, consent=True,  # noqa: F811
              factory=None):
    """Finestra con un profilo attivo (impostazioni scritte prima dell'avvio) e il provider simulato a copione
    (``factory``: un altro adattatore, es. quello vero del 30 verso un servizio simulato)."""
    profile = ProviderProfile("openai_compatible", url, MODEL)
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    settings.setValue("assistant/profiles", json.dumps({profile.id: entry_for(url)}))
    settings.setValue("assistant/active", profile.id)
    if consent:
        settings.setValue("assistant/consents", json.dumps(
            {profile.id: {"version": 1, "given_at": "2026-10-22T00:00:00+00:00"}}))
    settings.sync()
    keychain = FakeKeychain({profile.id: SECRET} if key else {})
    adapters = {}

    def scripted(p, kc):
        if p.id not in adapters:
            adapters[p.id] = ScriptedAdapter(script, kind=p.kind, base_url=p.base_url, model=p.model, keychain=kc)
        return adapters[p.id]

    win = make_window(qtbot, settings_path, cache, keychain=keychain, ai_adapter_factory=factory or scripted)
    return win, adapters, keychain


@pytest.fixture
def closing():
    windows = []
    yield windows
    for win in windows:
        win.confirm = lambda *a: True
        win.close()


def ask(qtbot, win, text, *, timeout=20000):
    panel = win.ai_panel
    count = len(panel.answers)
    panel.input.setPlainText(text)
    panel.send_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) > count, timeout=timeout)
    wait_idle(qtbot, win)
    return panel.answers[-1]


def cards(win, cls):
    return win.ai_panel.messages.findChildren(cls)


# =============================================================================
# T1 — pannello e voce di menu


def test_t1_panel_and_menu(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache)
    closing.append(win)
    dock = win.docks["assistant"]
    assert dock.widget() is win.ai_panel and win.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert 380 <= dock.width() <= 420 and dock.minimumWidth() == 380 and dock.maximumWidth() == 420
    action = win.panel_actions["assistant"]
    assert action.isEnabled() and action.shortcut().toString() == "Meta+Ctrl+A"
    panel = win.ai_panel
    assert panel.profile_label.text() == f"api.example.invalid · {MODEL}"
    assert panel.lock.toolTip() == "key in the Keychain" and panel.bottom.currentIndex() == 0
    assert "never files, pixels, keys or folders" in panel.privacy.text()
    action.trigger()  # richiudibile, con un comando ui.set_panel
    wait_idle(qtbot, win)
    assert not dock.isVisible()


# =============================================================================
# T2 — schede dei comandi; T6 — Cosa è stato inviato


def test_t2_command_cards_and_t6_sent(qtbot, settings_path, cache, closing):  # noqa: F811
    script = [calls_turn(tool_call("a", "view__set_grid", visible=True), tool_call("b", "layer__list")),
              lambda m, t, c: text_turn(f"Griglia accesa (#{numbers_sent(m)[0]}).")]
    win, adapters, _ = ai_window(qtbot, settings_path, cache, script)
    closing.append(win)
    answer = ask(qtbot, win, "Accendi la griglia ed elenca i livelli")
    assert answer.error is None
    first, second = cards(win, CommandCard)
    numbers = [e.number for e in win.session.history if e.command.requested_by.source == "ai"]
    assert [first.number, second.number] == numbers
    assert first.head.text() == f"#{numbers[0]}  view.set_grid" and first.params.text() == "visible = true · frame = icrs"
    assert first.result.text().startswith("→ ") and first.source.text().startswith("module ")
    assert second.head.text() == f"#{numbers[1]}  layer.list"
    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)  # clic → riga del pannello Comandi
    assert [e.number for e in win.history.selected()] == [numbers[1]]
    texts = win.ai_panel.messages.findChildren(MessageView)
    assert texts[-1].toPlainText() == f"Griglia accesa (#{numbers[0]})."
    # "#n" è una citazione (34, eccezione X1): nessun numero da verificare
    assert win.ai_panel.findChild(type(win.ai_panel.privacy), "verifySummary").text() == "no number to verify"
    assert "input tokens" in win.ai_panel.findChild(type(win.ai_panel.privacy), "aiTokens").text()
    # T6: JSON identico al RequestRecord, nessuna chiave
    dialog = win.ai_panel.show_sent(answer)
    adapter = next(iter(adapters.values()))
    sent = json.loads(dialog.json_text())
    assert [s["body"] for s in sent] == [r.body for r in adapter.records] == [r.body for r in answer.requests]
    assert [s["url"] for s in sent] == [r.url for r in answer.requests]
    assert SECRET not in dialog.text.toPlainText() and dialog.text.isReadOnly()
    dialog.copy()
    assert json.loads(QApplication.clipboard().text()) == sent
    dialog.close()


# =============================================================================
# T3 — conferma; T4 — conferma dopo testo esterno


def test_t3_confirmation_card(qtbot, settings_path, cache, closing, offline):  # noqa: F811
    load = region_command()
    script = [calls_turn(tool_call("c1", "catalog__load_region", **load)), text_turn("Non caricato."),
              calls_turn(tool_call("c2", "catalog__load_region", **load)), text_turn("Caricato.")]
    win, _, _ = ai_window(qtbot, settings_path, cache, script)
    closing.append(win)
    panel = win.ai_panel
    panel.input.setPlainText("Carica 2MASS")
    panel.send_button.click()
    qtbot.waitUntil(lambda: bool(cards(win, ConfirmationCard)), timeout=15000)
    card, = cards(win, ConfirmationCard)
    assert panel.send_button.text() == "Stop"
    assert card.request["command"] == "catalog.load_region"
    assert "radius = 30.0 arcsec" in card.params.text()
    assert card.max_rows.text() == "at most 100000 rows"
    assert card.reason.text() == "Confirmation needed: uses the network; long command"
    assert [b.text() for b in card.findChildren(QPushButton)] == [
        "Confirm", "Cancel", "Confirm for this conversation"]
    assert card.confirm_button.isDefault()
    card.cancel_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=15000)
    assert card.state.text() == "not confirmed" and not card.confirm_button.isEnabled()
    refused, = cards(win, CommandCard)
    assert refused.number is None and refused.result.text().startswith("TOOL_NOT_CONFIRMED")
    assert not any(e.command.requested_by.source == "ai" for e in win.session.history)
    # seconda risposta: Conferma → comando eseguito nella coda con requested_by = ai
    panel.input.setPlainText("Carica 2MASS, confermo")
    panel.send_button.click()
    qtbot.waitUntil(lambda: len(cards(win, ConfirmationCard)) == 2, timeout=15000)
    cards(win, ConfirmationCard)[1].confirm_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 2, timeout=20000)
    wait_idle(qtbot, win)
    entry, = [e for e in win.session.history if e.command.requested_by.source == "ai"]
    assert entry.command.name == "catalog.load_region" and cards(win, CommandCard)[1].number == entry.number
    assert "confirmed by the user" in cards(win, CommandCard)[1].head.text()


def test_t4_confirmation_after_external_text(qtbot, settings_path, cache, closing, tmp_path):  # noqa: F811
    path = write_catalog(tmp_path / "pleiadi_injection.xml", INJECTION_ROWS)
    script = [calls_turn(tool_call("c1", "catalog__rows", layer="L1")),
              calls_turn(tool_call("c2", "layer__set_opacity", layer="L1", opacity=0)),  # il modello obbedisce
              text_turn("Ho letto il catalogo.")]
    win, _, _ = ai_window(qtbot, settings_path, cache, script)
    closing.append(win)
    win.submit("catalog.open_file", {"file": {"path": str(path)}})
    wait_idle(qtbot, win)
    opacity = win.session.workspace.state.layer("L1").opacity
    panel = win.ai_panel
    panel.input.setPlainText("Leggi le righe di L1")
    panel.send_button.click()
    qtbot.waitUntil(lambda: bool(cards(win, ConfirmationCard)), timeout=15000)
    card, = cards(win, ConfirmationCard)
    assert card.conversation_button is None  # mai "per questa conversazione" dopo un testo esterno
    assert [b.text() for b in card.findChildren(QPushButton)] == ["Confirm", "Cancel"]
    assert "asked after reading external text (pleiadi_injection.xml)" in card.reason.text()
    card.cancel_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=15000)
    wait_idle(qtbot, win)
    assert win.session.workspace.state.layer("L1").opacity == opacity
    assert INJECTION not in "".join(v.toPlainText() for v in panel.messages.findChildren(MessageView))


# =============================================================================
# T7 — chiave; T15 — scelta del provider


def test_t7_key_only_in_keychain(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, keychain = ai_window(qtbot, settings_path, cache, key=False)
    closing.append(win)
    dialog = win.ai_panel.open_settings()
    profile_id = ProviderProfile("openai_compatible", REMOTE, MODEL).id
    assert dialog.key.echoMode() == dialog.key.EchoMode.Password
    assert dialog.key_state.text() == f"No key for {profile_id} in the Keychain."
    new_key = "sk-nuova-chiave-9876543210"
    dialog.key.setText(new_key)
    dialog.findChild(QPushButton, "saveKey").click()
    assert keychain.keys == {profile_id: new_key}
    assert dialog.key.text() == "" and not dialog.key.isUndoAvailable()
    assert dialog.key_state.text() == f"A key for {profile_id} is in the Keychain."
    dialog.strict.setChecked(True)
    dialog.max_calls.setValue(7)
    dialog.price_in.setText("3.0")
    dialog.price_out.setText("15.0")
    dialog.currency.setText("USD")
    from PySide6.QtWidgets import QDialogButtonBox

    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    wait_idle(qtbot, win)
    prefs = [e for e in win.session.history.entries if e.command.name == "prefs.set"]
    assert {e.command.parameters["key"] for e in prefs} == {"assistant/profiles", "assistant/strict",
                                                            "assistant/max_calls"}
    assert all(e.command_class == "application" and e.result.status == "ok" for e in prefs)
    assert new_key not in json.dumps([e.to_json() for e in win.session.history.entries])
    win.settings.sync()
    with open(settings_path, encoding="utf-8") as f:
        assert new_key not in f.read()  # la chiave non è in QSettings
    assert win.ai_panel.assistant.strict and win.ai_panel.assistant.limits.max_calls == 7
    pricing = win.ai_panel.assistant.pricing
    assert (pricing.input_per_million, pricing.output_per_million, pricing.currency) == (3.0, 15.0, "USD")
    assert win.ai_panel.lock.toolTip() == "key in the Keychain"


def test_t15_provider_menu(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, keychain = ai_window(qtbot, settings_path, cache)
    closing.append(win)
    keychain.keys["anthropic"] = "sk-ant-finta"
    dialog = win.ai_panel.open_settings()
    items = [dialog.provider.itemText(i) for i in range(dialog.provider.count())]
    assert items == [p.provider for p in PROVIDER_PRESETS] + ["Other OpenAI-compatible endpoint…"]
    for i, preset in enumerate(PROVIDER_PRESETS):
        dialog.provider.setCurrentIndex(i)
        assert dialog.base_url.text() == preset.base_url
        assert dialog.model.currentText() == ""  # nessun modello preselezionato
        if preset.tool_calling == "verified":
            assert dialog.badge.isHidden()
        else:
            assert not dialog.badge.isHidden() and dialog.badge.text() == dialog.status_texts[preset.tool_calling]
            assert dialog.provider.itemData(i, Qt.ItemDataRole.ToolTipRole).endswith(" ".join(preset.sources))
        if preset.preset == "anthropic":
            assert dialog.key_state.text() == "A key for anthropic is in the Keychain."
        elif preset.preset == "openai":
            assert dialog.key_state.text() == "No key for openai-compatible:api.openai.com in the Keychain."
        elif preset.preset == "ollama":
            assert "not needed by most local servers" in dialog.key_state.text()
    dialog.provider.setCurrentIndex(len(PROVIDER_PRESETS))
    assert dialog.base_url.text() == "" and not dialog.badge.isHidden()
    dialog.base_url.setText("http://example.org/v1")  # endpoint remoto in http: rifiuto (AI_INSECURE_ENDPOINT)
    dialog.model.setEditText("m")
    from PySide6.QtWidgets import QDialogButtonBox

    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    assert "AI_INSECURE_ENDPOINT" in dialog.error.text() and dialog.isVisible()
    dialog.reject()


# =============================================================================
# T8 — consenso; T9 — non disponibile; T11 — locale


def test_t8_consent(qtbot, settings_path, cache, closing):  # noqa: F811
    win, adapters, _ = ai_window(qtbot, settings_path, cache, [text_turn("Ciao."), text_turn("Ancora.")],
                                 consent=False)
    closing.append(win)
    panel = win.ai_panel
    adapter = next(iter(adapters.values()))
    assert panel.bottom.currentIndex() == 0  # il campo resta: il consenso si chiede al primo messaggio
    panel.input.setPlainText("Ciao")
    panel.send_button.click()
    dialog = panel.consent_dialog
    assert dialog.isVisible() and dialog.isModal()
    assert "api.example.invalid" in dialog.label.text() and "API keys" in dialog.label.text()
    dialog.later_button.click()  # Non ora: nulla inviato
    assert adapter.requests == [] and panel.bottom.currentIndex() == 1
    assert "AI_CONSENT_REQUIRED: The consent to send data to api.example.invalid has not been given." in \
        panel.unavailable.text()
    assert panel.fix_button.text() == "Give consent…"
    panel.input.setPlainText("Ciao di nuovo")
    panel.bottom.setCurrentIndex(0)
    panel.send_button.click()
    panel.consent_dialog.accept_button.click()  # Accetto: consenso salvato, poi il messaggio parte
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=15000)
    wait_idle(qtbot, win)
    assert len(adapter.requests) == 1 and panel.answers[0].text == "Ciao."
    saved = json.loads(win.settings.value("assistant/consents"))
    assert saved[adapter.profile.id]["version"] == 1 and saved[adapter.profile.id]["given_at"].endswith("+00:00")
    consent, = [e for e in win.session.history if e.command.name == "prefs.set"]
    assert consent.command.parameters["key"] == "assistant/consents" and consent.command_class == "application"


def test_t9_unavailable(qtbot, settings_path, cache, closing):  # noqa: F811
    win, adapters, _ = ai_window(qtbot, settings_path, cache, key=False)
    closing.append(win)
    panel = win.ai_panel
    assert panel.bottom.currentIndex() == 1
    assert panel.unavailable.text() == (
        "The assistant is not available. KEY_NOT_FOUND: There is no key in the Keychain for profile "
        "openai-compatible:api.example.invalid. The rest of AstroTwo works normally.")
    assert panel.fix_button.text() == "Open assistant settings…"
    assert panel.lock.toolTip() == "no key in the Keychain"
    win.act_grid.trigger()  # il resto della finestra funziona
    wait_idle(qtbot, win)
    assert win.session.history.entries[-1].command.name == "view.set_grid"
    assert next(iter(adapters.values())).requests == []
    panel.fix_button.click()
    assert panel.settings_dialog.isVisible()
    panel.settings_dialog.reject()


def test_no_profile(qtbot, settings_path, cache, closing):  # noqa: F811
    win = make_window(qtbot, settings_path, cache, keychain=FakeKeychain())
    closing.append(win)
    assert win.ai_panel.profile_label.text() == "No profile"
    assert "AI_NO_PROFILE: No profile is configured." in win.ai_panel.unavailable.text()


def test_t11_local(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache, [text_turn("Locale.")], url=LOCAL, key=False)
    closing.append(win)
    panel = win.ai_panel
    assert not panel.local_badge.isHidden() and panel.local_badge.text() == "local · nothing leaves the Mac"
    assert panel.bottom.currentIndex() == 0  # un server locale non chiede la chiave
    assert ask(qtbot, win, "Ciao").text == "Locale."


# =============================================================================
# T10 — Stop; T12 — collegamenti e HTML


def test_t10_stop(qtbot, settings_path, cache, closing):  # noqa: F811
    started = threading.Event()

    def slow(messages, tools, cancel):
        yield TextDelta("Comincio")
        started.set()
        while not cancel.cancelled:
            time.sleep(0.01)
        yield TurnEnd("cancelled")

    win, _, _ = ai_window(qtbot, settings_path, cache, [slow])
    closing.append(win)
    panel = win.ai_panel
    panel.input.setPlainText("Racconta")
    panel.send_button.click()
    assert started.wait(10)
    qtbot.waitUntil(lambda: panel.send_button.text() == "Stop", timeout=5000)
    assert not panel.new_button.isEnabled()
    panel.send_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=10000)
    assert panel.send_button.text() == "Send" and panel.new_button.isEnabled()
    notes = [label.text() for label in panel.messages.findChildren(type(panel.privacy), "aiLimitNote")]
    assert notes == ["Answer interrupted."]
    assert panel.answers[0].interrupted


def test_t12_links_and_html(qtbot, settings_path, cache, closing):  # noqa: F811
    text = ("Vedi [la pagina](http://evil.example/x) e http://bare.example/y.\n\n<b>grassetto</b> <script>x</script>"
            "\n\n![immagine](http://img.example/a.png)\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    win, _, _ = ai_window(qtbot, settings_path, cache, [text_turn(text)])
    closing.append(win)
    opened = []
    ask(qtbot, win, "Mostra")
    view = win.ai_panel.messages.findChildren(MessageView)[-1]
    view.opener = opened.append
    shown = view.toPlainText()
    assert "la pagina <http://evil.example/x>" in shown  # indirizzo scritto per intero
    assert "<b>grassetto</b> <script>x</script>" in shown  # HTML mostrato come testo
    assert "[image not shown: http://img.example/a.png]" in shown and "<img" not in view.toHtml()
    assert opened == []  # nulla si apre da solo
    view.anchorClicked.emit(QUrl("file:///etc/passwd"))
    view.anchorClicked.emit(QUrl("http://evil.example/x"))  # clic dell'utente: solo http(s)
    assert opened == [QUrl("http://evil.example/x")]


# =============================================================================
# T13 — modalità notte; sessione con il testo delle conversazioni


def link_colors(view):
    """Colori del testo dei collegamenti nel documento di un messaggio."""
    out, block = [], view.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fmt = it.fragment().charFormat()
            if fmt.isAnchor():
                out.append(fmt.foreground().color())
            it += 1
        block = block.next()
    return out


def test_t13_night_mode(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache, [text_turn("Vedi http://example.org/pagina")])
    closing.append(win)
    ask(qtbot, win, "Un collegamento")
    view = win.ai_panel.messages.findChildren(MessageView)[-1]
    assert any(c.blue() > 200 for c in link_colors(view))  # accento blu nel tema scuro
    win.act_night.trigger()
    wait_idle(qtbot, win)
    colors = link_colors(view)
    assert colors and all(c.green() <= NIGHT_THRESHOLD and c.blue() <= NIGHT_THRESHOLD for c in colors)
    colors = list(stylesheet_colors(win.ai_panel.styleSheet()))
    assert len(colors) > 5
    assert all(g <= NIGHT_THRESHOLD and b <= NIGHT_THRESHOLD for _, g, b in colors), colors
    for button in (win.ai_panel.new_button, win.ai_panel.settings_button, win.ai_panel.send_button):
        image = button.icon().pixmap(32, 32).toImage()
        drawn = [image.pixelColor(x, y) for x in range(32) for y in range(32) if image.pixelColor(x, y).alpha()]
        assert drawn and all(c.green() <= NIGHT_THRESHOLD and c.blue() <= NIGHT_THRESHOLD for c in drawn)


def test_session_with_conversations(qtbot, settings_path, cache, closing, tmp_path):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache, [text_turn("Ciao.")])
    closing.append(win)
    ask(qtbot, win, "Ciao")
    without, with_text = tmp_path / "a.astrotwo.json", tmp_path / "b.astrotwo.json"
    assert win.save_session(str(without)) and win.save_session(str(with_text), include_conversations=True)
    assert "conversations" not in json.loads(without.read_text(encoding="utf-8"))
    block, = json.loads(with_text.read_text(encoding="utf-8"))["conversations"]
    assert [m["role"] for m in block["messages"]] == ["user", "assistant"]
    assert block["answers"][0]["text"] == "Ciao." and SECRET not in with_text.read_text(encoding="utf-8")


def test_new_conversation(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache, [text_turn("Uno."), text_turn("Due.")])
    closing.append(win)
    panel = win.ai_panel
    first = panel.assistant.conversation
    ask(qtbot, win, "Uno")
    panel.new_button.click()
    assert first.closed and panel.assistant.conversation is not first
    qtbot.waitUntil(lambda: panel.messages.findChildren(MessageView) == [], timeout=5000)
    assert panel.answers == []


def test_italian(qtbot, settings_path, cache, closing):  # noqa: F811
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win, _, _ = ai_window(qtbot, settings_path, cache, key=False)
    closing.append(win)
    try:
        panel = win.ai_panel
        assert win.language == "it" and panel.send_button.text() == "Invia"
        assert panel.unavailable.text().startswith(
            "L'assistente non è disponibile. KEY_NOT_FOUND: Nessuna chiave nel Portachiavi per il profilo")
        assert panel.privacy.text().startswith("Al provider vanno il testo e i risultati dei comandi")
        unverified = CheckedNumber(WrittenNumber("7", 0, 1, "decimal"), "not_verified")
        assert panel.number_tooltip(unverified) == ("Non viene da un comando", None)
    finally:
        from astrotwo.ui.main_window import load_translations

        load_translations("en")


# =============================================================================
# T5 — evidenziazione dei numeri (sprint 7b)


def marked(view):
    """Frammenti del documento con uno stato del 34: (testo, stato, sottolineatura, sfondo, suggerimento, formato)."""
    out, block = [], view.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            fmt = fragment.charFormat()
            state = fmt.property(MARK_STATE_PROPERTY)
            if state:
                brush = fmt.background()
                alpha = brush.color().alpha() if brush.style() != Qt.BrushStyle.NoBrush else 0
                out.append((fragment.text(), state, fmt.underlineStyle(), alpha, fmt.toolTip(), fmt))
            it += 1
        block = block.next()
    return out


SOLID = QTextCharFormat.UnderlineStyle.SingleUnderline
DASHED = QTextCharFormat.UnderlineStyle.DashUnderline
WAVE = QTextCharFormat.UnderlineStyle.WaveUnderline


def no_markers(view):
    return not any(0xE000 <= ord(c) <= 0xE019 for c in view.toPlainText())


def test_t5_highlight_from_the_answer(qtbot, settings_path, cache, closing):  # noqa: F811
    """Flusso vero: comandi del 05, rapporto del 34, stili e suggerimenti nel documento della risposta."""
    def answer(messages, tools, cancel):
        a, b = numbers_sent(messages)
        return text_turn(f"**Risultato:** 24 (#{a}).\n\nCon #{a} la conversione dà 100000000 nm.\n\n"
                         f"Hai scritto 42; `7.25` invece è mio, e 1,5 è dubbio. Vedi https://example.org/p/9.75 ora.")

    script = [calls_turn(tool_call("a", "calc__evaluate_expression", expression="3*8"),
                         tool_call("b", "calc__convert_units", value=0.1, from_unit="m", to_unit="nm")), answer]
    win, _, _ = ai_window(qtbot, settings_path, cache, script)
    closing.append(win)
    result = ask(qtbot, win, "Calcola 3*8 e converti 0.1 m in nm; il mio numero è 42")
    a = result.calls[0].number
    states = [(n.number.text, n.state) for n in result.report.numbers]
    assert states == [("24", "verified"), (f"#{a}", "excluded"), (f"#{a}", "excluded"),
                      ("100000000", "verified_other_command"), ("42", "user_input"), ("7.25", "not_verified"),
                      ("1,5", "ambiguous"), ("9.75", "not_verified")]
    view = win.ai_panel.messages.findChildren(MessageView)[-1]
    assert no_markers(view)  # i segni invisibili sono tolti
    assert "Risultato: 24 (#" in view.toPlainText() and "https://example.org/p/9.75" in view.toPlainText()
    got = {text: (state, style, alpha) for text, state, style, alpha, _, _ in marked(view)}
    assert got == {"24": ("verified", SOLID, 0), "100000000": ("verified_other_command", SOLID, 0),
                   "42": ("user_input", DASHED, 0), "7.25": ("not_verified", WAVE, 77),
                   "1,5": ("ambiguous", WAVE, 77), "9.75": ("not_verified", WAVE, 77)}
    tips = {text: tip for text, _, _, _, tip, _ in marked(view)}
    full = repr(result.report.numbers[0].matched_value)
    assert tips["24"] == f"Verified: {full} · command #{a} · module 18 evaluate_expression"
    assert tips["100000000"].startswith("Verified with another command: ")
    assert tips["42"] == "From your message" and tips["1,5"] == "Ambiguous format"
    assert tips["7.25"] == "Does not come from a command"
    # l'indirizzo con il numero resta un collegamento intero (nessun segno dentro)
    fmt = next(f for t, *_, f in marked(view) if t == "9.75")
    assert fmt.isAnchor() and fmt.anchorHref() == "https://example.org/p/9.75"
    summary = win.ai_panel.findChild(type(win.ai_panel.privacy), "verifySummary").text()
    assert summary.startswith("⚠ 3 of 5 numbers do not come from a command") and "+ 1 from your message" in summary


def report_for(text, items):
    """Rapporto del 34 scritto nel test: ``items`` = (sottostringa, stato, comando, valore, unità, fonte)."""
    numbers, start = [], 0
    for sub, state, command, value, unit, source in items:
        start = text.index(sub, start)
        written = WrittenNumber(sub, start, start + len(sub), "decimal")
        numbers.append(CheckedNumber(written, state, command, value, unit, None, source))
        start += len(sub)
    return VerificationReport(text, tuple(numbers))


def test_t5_every_state_hover_copy_and_night(qtbot, settings_path, cache, closing):  # noqa: F811
    win, _, _ = ai_window(qtbot, settings_path, cache)
    closing.append(win)
    win.submit("view.set_grid", {"visible": True})  # #1 nella cronologia
    wait_idle(qtbot, win)
    text = ("Valori: **1.5** e 2.5\n\n| a | b |\n|---|---|\n| 3.5 | 4.5 |\n\n- 5.5 in un elenco\n\n"
            "`6.5` e 7,5 e #1 e [link](http://x.example/8.5)")
    report = report_for(text, [
        ("1.5", "verified", 1, 1.5000000001, "deg", None), ("2.5", "verified_other_command", 1, 2.5, None, None),
        ("3.5", "command_parameter", 1, 3.5, "arcmin", None), ("4.5", "user_input", None, 4.5, None, None),
        ("5.5", "external_text", 1, 5.5, None, "pleiadi.xml"), ("6.5", "not_verified", None, None, None, None),
        ("7,5", "ambiguous", None, None, None, None), ("#1", "excluded", None, None, None, None),
        ("8.5", "not_verified", None, None, None, None)])
    panel = win.ai_panel
    view = MessageView(text)
    view.mark_colors = panel._mark_colors()
    panel._add(view)
    qtbot.waitUntil(lambda: view.isVisible() and view.width() > 100, timeout=5000)
    panel._show_marks([view], report)
    assert no_markers(view)
    got = [(t, state, style, alpha) for t, state, style, alpha, _, _ in marked(view)]
    assert got == [("1.5", "verified", SOLID, 0), ("2.5", "verified_other_command", SOLID, 0),
                   ("3.5", "command_parameter", DASHED, 0), ("4.5", "user_input", DASHED, 0),
                   ("5.5", "external_text", DASHED, 0), ("6.5", "not_verified", WAVE, 77),
                   ("7,5", "ambiguous", WAVE, 77), ("8.5", "not_verified", WAVE, 77)]  # #1 escluso: nessuno stile
    tips = [tip for *_, tip, _ in marked(view)]
    assert tips[0] == ("Verified: 1.5000000001 deg · command #1 · module 10 choose_grid_spacing · "
                       "module 10 compute_grid_lines")
    assert tips[1] == "Verified with another command: 2.5 · command #1 · module 10 choose_grid_spacing · " \
        "module 10 compute_grid_lines"
    assert tips[3] == "From your message" and tips[5] == tips[7] == "Does not come from a command"
    assert tips[6] == "Ambiguous format"
    assert tips[2] == "Parameter of command #1: 3.5 arcmin"
    assert tips[4] == "From external text, not computed (pleiadi.xml)"
    # passaggio del mouse: il numero sotto il punto; clic destro: copia del valore pieno
    start = view.toPlainText().index("1.5")
    cursor = QTextCursor(view.document())
    cursor.setPosition(start)
    left = view.cursorRect(cursor)
    cursor.setPosition(start + 1)
    point = QPoint((left.x() + view.cursorRect(cursor).x()) // 2, left.center().y())
    mark = view.mark_at(point)
    assert mark is not None and mark.state == "verified" and mark.full_value == "1.5000000001 deg"
    menu = view.mark_menu(point)
    copy = next(a for a in menu.actions() if a.objectName() == "copyFullValue")
    copy.trigger()
    assert QApplication.clipboard().text() == "1.5000000001 deg"
    next(a for a in menu.actions() if a.objectName() == "copyNote").trigger()
    assert QApplication.clipboard().text() == mark.tooltip
    assert view.mark_at(QPoint(view.width() - 2, view.height() - 2)) is None
    # modalità notte: stessi stili, solo toni di rosso; il collegamento resta intero
    win.act_night.trigger()
    wait_idle(qtbot, win)
    after = marked(view)
    assert [(t, s, st, a) for t, s, st, a, _, _ in after] == got
    for *_, fmt in after:
        for color in (fmt.underlineColor(), fmt.background().color()):
            assert color.green() <= NIGHT_THRESHOLD and color.blue() <= NIGHT_THRESHOLD
    assert "link <http://x.example/8.5>" in view.toPlainText()


# =============================================================================
# T14 — reattività: risposta lenta e comando lungo


def test_t14_latency(qtbot, settings_path, cache, closing, monkeypatch):  # noqa: F811
    from astrotwo.core import catalogs

    running = []

    def slow_catalog(*a, **k):
        running.append(time.monotonic())
        time.sleep(2.0)  # comando lungo nel thread dei comandi
        raise catalogs.CatalogsError("CATALOG_UNKNOWN", "catalogo finto e lento",
                                     params={"reason": "invalid_id", "catalog_id": "'finto'"})

    def slow_text(messages, tools, cancel):
        for _ in range(60):
            yield TextDelta("parola ")
            time.sleep(0.02)  # risposta che arriva lentamente, a pezzi
        yield from calls_turn(tool_call("c1", "catalog__load_region", **region_command()))

    monkeypatch.setattr(catalogs, "load_catalog", slow_catalog)
    win, _, _ = ai_window(qtbot, settings_path, cache, [slow_text, text_turn("Fatto.")])
    closing.append(win)
    gaps, clock = [], QElapsedTimer()
    probe = QTimer()
    probe.setInterval(10)
    probe.timeout.connect(lambda: gaps.append(clock.restart()))
    clock.start()
    probe.start()
    panel = win.ai_panel
    panel.input.setPlainText("Carica 2MASS lentamente")
    panel.send_button.click()
    qtbot.waitUntil(lambda: bool(cards(win, ConfirmationCard)), timeout=15000)
    cards(win, ConfirmationCard)[0].confirm_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=20000)
    probe.stop()
    assert running and len(gaps) > 100
    assert max(gaps[1:]) < 100, max(gaps)  # sonda di latenza del thread principale (§9)
    assert panel.answers[0].text.endswith("Fatto.")
    assert cards(win, CommandCard)[0].result.text().startswith("CATALOG_UNKNOWN")


# =============================================================================
# Aggiorna e "Prova il modello" con il servizio simulato del 30; errori del provider; conversazione troppo lunga


def local_window(qtbot, settings_path, cache, service):  # noqa: F811
    return ai_window(qtbot, settings_path, cache, url=service.url + "/v1", factory=make_adapter)


def test_refresh_models_and_probe(qtbot, settings_path, cache, closing, provider_service):  # noqa: F811
    win, _, _ = local_window(qtbot, settings_path, cache, provider_service)
    closing.append(win)
    dialog = win.ai_panel.open_settings()
    listing = {"object": "list", "data": [{"id": "test-model", "object": "model", "created": 1, "owned_by": "x"},
                                          {"id": "altro-modello", "object": "model", "created": 1, "owned_by": "x"}]}
    provider_service.routes["/v1/models"] = [Reply(chunks=[json.dumps(listing)], ctype="application/json")]
    dialog.findChild(QPushButton, "refreshModels").click()
    qtbot.waitUntil(lambda: dialog.models_note.text() == "2 models from the provider.", timeout=10000)
    assert [dialog.model.itemText(i) for i in range(dialog.model.count())] == ["test-model", "altro-modello"]
    assert dialog.model.currentText() == MODEL  # nessun modello scelto al posto dell'utente
    provider_service.routes["/v1/models"] = [error_reply("openai_compatible", 404, "not found")]
    dialog.findChild(QPushButton, "refreshModels").click()
    qtbot.waitUntil(lambda: dialog.models_note.text().startswith("AI_MODELS_UNAVAILABLE"), timeout=10000)
    probe = dialog.findChild(QPushButton, "probeModel")
    provider_service.script = [tools_reply("openai_compatible", [("c1", "astrotwo_probe", ["{}"])])]
    probe.click()
    qtbot.waitUntil(lambda: dialog.probe_state.text().startswith("The model called"), timeout=10000)
    assert dialog.probe_state.text() == "The model called the test tool. 11 input tokens, 22 output tokens"
    provider_service.script = [text_reply("openai_compatible", ["niente strumenti"])]
    probe.click()
    qtbot.waitUntil(lambda: dialog.probe_state.text().startswith("AI_NO_TOOLS"), timeout=10000)
    provider_service.script = [error_reply("openai_compatible", 401, "invalid api key")]
    probe.click()
    qtbot.waitUntil(lambda: dialog.probe_state.text().startswith("AI_AUTH"), timeout=10000)
    assert SECRET not in dialog.probe_state.text()
    assert not any(e.command.name == "prefs.set" for e in win.session.history)  # nessun comando registrato
    sent = [r for r in provider_service.requests if r["method"] == "POST"]
    assert sent and all(SECRET not in json.dumps(r["body"]) for r in sent)
    dialog.reject()


def test_provider_error_and_context_too_long(qtbot, settings_path, cache, closing):  # noqa: F811
    script = [[TextDelta("Inizio la risposta"), ProviderError(
        "AI_AUTH", "chiave rifiutata dal provider (401)", params={"status": 401, "detail": "rejected by the provider"})],
              [ProviderError("AI_CONTEXT_TOO_LONG", "conversazione oltre il contesto del modello",
                             params={"status": 400, "detail": "prompt is too long"})]]
    win, _, _ = ai_window(qtbot, settings_path, cache, script)
    closing.append(win)
    panel = win.ai_panel
    first = ask(qtbot, win, "Ciao")
    assert first.error.code == "AI_AUTH"
    errors = [label.text() for label in panel.messages.findChildren(type(panel.privacy), "aiError")]
    assert errors == ["AI_AUTH: The key is not valid or has no permissions (HTTP 401): rejected by the provider"]
    assert "Inizio la risposta" in panel.messages.findChildren(MessageView)[-1].toPlainText()
    assert panel.send_button.text() == "Send" and panel.bottom.currentIndex() == 0
    ask(qtbot, win, "Ancora")
    footer = panel.messages.findChildren(type(panel.privacy), "aiError")[-1]
    assert footer.text() == ("AI_CONTEXT_TOO_LONG: The conversation exceeds the context of the model (HTTP 400): "
                             "prompt is too long")
    again = next(b for b in panel.messages.findChildren(QPushButton) if b.text() == "New conversation")
    conversation = panel.assistant.conversation
    again.click()
    assert panel.assistant.conversation is not conversation
    qtbot.waitUntil(lambda: panel.messages.findChildren(MessageView) == [], timeout=5000)


# =============================================================================
# Conferma in attesa con il pannello chiuso; uscita con una risposta in corso (§10)


def test_confirmation_waits_with_panel_closed(qtbot, settings_path, cache, closing, offline):  # noqa: F811
    load = region_command()
    win, _, _ = ai_window(qtbot, settings_path, cache,
                          [calls_turn(tool_call("c1", "catalog__load_region", **load)), text_turn("Caricato.")])
    closing.append(win)
    panel = win.ai_panel
    panel.input.setPlainText("Carica 2MASS")
    panel.send_button.click()
    qtbot.waitUntil(lambda: bool(cards(win, ConfirmationCard)), timeout=15000)
    win.panel_actions["assistant"].trigger()  # pannello chiuso
    wait_idle(qtbot, win)
    assert not win.docks["assistant"].isVisible() and panel.busy
    qtbot.wait(300)
    assert panel.busy and panel.answers == []  # la conferma resta in attesa
    win.panel_actions["assistant"].trigger()
    wait_idle(qtbot, win)
    card, = cards(win, ConfirmationCard)
    assert win.docks["assistant"].isVisible() and card.isVisible() and card.choice is None
    card.confirm_button.click()
    qtbot.waitUntil(lambda: len(panel.answers) == 1, timeout=20000)
    assert panel.answers[0].text == "Caricato."


def test_quit_with_answer_in_progress(qtbot, settings_path, cache):  # noqa: F811
    started = threading.Event()

    def slow(messages, tools, cancel):
        yield TextDelta("Comincio")
        started.set()
        while not cancel.cancelled:
            time.sleep(0.01)
        yield TurnEnd("cancelled")

    win, _, _ = ai_window(qtbot, settings_path, cache, [slow])
    panel = win.ai_panel
    panel.input.setPlainText("Racconta")
    panel.send_button.click()
    assert started.wait(10)
    asked = []
    win.confirm = lambda title, text: asked.append(text) or False
    win.close()  # "No": l'app resta aperta e la risposta continua
    assert asked and "The assistant is answering: the answer will be stopped." in asked[0]
    assert win.isVisible() and panel.busy
    win.confirm = lambda *a: True
    win.close()
    qtbot.waitUntil(lambda: not panel.busy, timeout=10000)
    assert not win.isVisible() and panel.assistant.conversation.answers[-1].interrupted
