"""Offline real-widget regressions for the basic delivery policy."""
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import acceptance_gate as gate


@pytest.mark.parametrize('broken_score', [False, True])
def test_hidden_score_is_nonblocking_but_wrong_scoring_still_fails(tmp_path, broken_score):
    import tkinter as tk
    root = tk.Tk()
    root.geometry('600x500')
    app = SimpleNamespace(screen='menu', widgets={}, data_dir=tmp_path)

    def page(name):
        for child in root.winfo_children():
            child.destroy()
        app.screen, app.widgets = name, {}

    def control(role, widget):
        widget.pack()
        app.widgets[role] = widget
        return widget

    def play():
        page('play')
        questions = [SimpleNamespace(id=str(i), prompt='1/2 + 1/4', answer=Fraction(3, 4)) for i in range(2)]
        session = SimpleNamespace(questions=questions, index=0, correct=0, attempted=0, answered=False)
        session.current = lambda: questions[session.index] if session.index < len(questions) else None
        app.session = session
        control('question', tk.Label(root, text=questions[0].prompt))
        answer = control('answer', tk.Entry(root))
        control('score', tk.Label(root, text='Score: 0')).pack_forget()
        feedback = control('feedback', tk.Label(root, text=''))

        def check():
            if session.answered:
                return
            try:
                value = Fraction(answer.get())
            except (ValueError, ZeroDivisionError):
                feedback.configure(text='Enter a fraction')
                return
            session.correct += int(value == session.current().answer and not broken_score)
            session.attempted += 1
            session.answered = True
            feedback.configure(text='Checked')

        def advance():
            if not session.answered:
                return
            session.index += 1
            session.answered = False
            if session.index == len(questions):
                page('results')
                control('summary', tk.Label(root, text=f'{session.correct}/{len(questions)}'))
                control('replay', tk.Button(root, text='Again', command=play))
            else:
                answer.delete(0, 'end')

        control('check', tk.Button(root, text='Check', command=check))
        control('next', tk.Button(root, text='Next', command=advance))

    control('play', tk.Button(root, text='Play', command=play))
    store = SimpleNamespace(Store=lambda _: SimpleNamespace(load_scores=lambda: []))
    try:
        with patch.dict('sys.modules', {'storage': store}):
            if broken_score:
                with pytest.raises(gate.AcceptanceFailure, match='scores once'):
                    gate.check_app(root, app, basic=True)
            else:
                report = gate.check_app(root, app, basic=True)
                assert report['status'] == 'passed'
                assert any('Score display' in w for w in report['warnings'])
                assert any('Score history' in w for w in report['warnings'])
                assert 'admin' not in app.widgets  # No editor/help traversal needed.
    finally:
        root.destroy()


def test_late_score_label_stays_near_the_top(tmp_path):
    import tkinter as tk
    from foundation.forge_ui import GameShell
    root = tk.Tk()
    app = GameShell(root, tmp_path)
    try:
        app.page('play', 'Fixture')
        app.draw_question('1/2 + 1/4')
        for i in range(15):
            app.label('extra'+str(i), 'Extra generated text')
        score = app.label('score', '1/2')
        root.update()
        assert score.winfo_ismapped()
        assert score.winfo_y() < 150
    finally:
        app.close()
