from fasthtml.common import *

# --- 1. CSS STYLING ---
# We inject the CSS directly into the head
app_css = Style("""
    :root {
        --primary: #0a66c2;
        --bg: #f8f9fa;
        --surface: #ffffff;
        --border: #e0e0e0;
    }
    body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); color: #191919; display: flex; justify-content: center; min-height: 100vh; padding: 20px; }
    .app-container { background: var(--surface); width: 100%; max-width: 750px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid var(--border); overflow: hidden; display: flex; flex-direction: column; }
    
    .header { padding: 24px 32px; border-bottom: 1px solid var(--border); background: #fff; }
    .header h1 { margin: 0; color: var(--primary); font-size: 1.4rem; font-weight: 700; }
    
    .toolbar-group { padding: 12px 24px; border-bottom: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background: #fff; }
    .label { font-size: 0.75rem; font-weight: 600; color: #999; text-transform: uppercase; margin-right: 8px; }
    
    button.tool-btn { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 8px 14px; cursor: pointer; transition: 0.2s; color: #444; }
    button.tool-btn:hover { background: #eef3f8; border-color: var(--primary); color: var(--primary); }
    
    .editor-wrapper { background: #fafafa; position: relative; }
    textarea { width: 100%; height: 320px; border: none; padding: 32px; font-size: 1.05rem; line-height: 1.6; outline: none; background: transparent; resize: none; font-family: inherit; }
    
    .footer { padding: 16px 32px; background: #fff; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .btn-primary { background: var(--primary); color: white; border: none; padding: 12px 28px; border-radius: 30px; font-weight: 600; cursor: pointer; }
    .btn-primary:hover { background: #004182; }
    
    .toast { position: fixed; bottom: 40px; left: 50%; transform: translate(-50%, 20px); background: #333; color: white; padding: 12px 24px; border-radius: 50px; opacity: 0; transition: all 0.3s ease; pointer-events: none; }
    .toast.visible { opacity: 1; transform: translate(-50%, 0); }
""")

# --- 2. JAVASCRIPT LOGIC ---
# This logic runs in the browser to handle selection and Unicode mapping
client_logic = Script("""
    const maps = {
        boldSans: {
            a: '𝗮', b: '𝗯', c: '𝗰', d: '𝗱', e: '𝗲', f: '𝗳', g: '𝗴', h: '𝗵', i: '𝗶', j: '𝗷', k: '𝗸', l: '𝗹', m: '𝗺', n: '𝗻', o: '𝗼', p: '𝗽', q: '𝗾', r: '𝗿', s: '𝘀', t: '𝘁', u: '𝘂', v: '𝘃', w: '𝘄', x: '𝘅', y: '𝘆', z: '𝘇',
            A: '𝗔', B: '𝗕', C: '𝗖', D: '𝗗', E: '𝗘', F: '𝗙', G: '𝗚', H: '𝗛', I: '𝗜', J: '𝗝', K: '𝗞', L: '𝗟', M: '𝗠', N: '𝗡', O: '𝗢', P: '𝗣', Q: '𝗤', R: '𝗥', S: '𝗦', T: '𝗧', U: '𝗨', V: '𝗩', W: '𝗪', X: '𝗫', Y: '𝗬', Z: '𝗭'
        },
        italicSans: {
            a: '𝘢', b: '𝘣', c: '𝘤', d: '𝘥', e: '𝘦', f: '𝘧', g: '𝘨', h: '𝘩', i: '𝘪', j: '𝘫', k: '𝘬', l: '𝘭', m: '𝘮', n: '𝘯', o: '𝘰', p: '𝘱', q: '𝘲', r: '𝘳', s: '𝘴', t: '𝘵', u: '𝘶', v: '𝘷', w: '𝘸', x: '𝘹', y: '𝘺', z: '𝘻',
            A: '𝘈', B: '𝘉', C: '𝘊', D: '𝘋', E: '𝘌', F: '𝘍', G: '𝘎', H: '𝘏', I: '𝘐', J: '𝘑', K: '𝘒', L: '𝘓', M: '𝘔', N: '𝘕', O: '𝘖', P: '𝘗', Q: '𝘘', R: '𝘙', S: '𝘚', T: '𝘛', U: '𝘜', V: '𝘝', W: '𝘞', X: '𝘟', Y: '𝘠', Z: '𝘡'
        }
    };
    
    const buzzwords = { "growth": "📈", "team": "🤝", "hiring": "📢", "jobs": "💼", "work": "🛠️", "tech": "🤖", "data": "📊", "idea": "💡", "win": "🏅" };

    function getEditor() { return document.getElementById('editor'); }

    function applyFormat(type) {
        const editor = getEditor();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const text = editor.value.substring(start, end);
        if(!text) return;

        let res = '';
        if(type === 'underline') {
            for(let char of text) res += char + '\\u0332';
        } else {
            const map = maps[type];
            for(let char of text) res += map[char] || char;
        }
        
        editor.value = editor.value.substring(0, start) + res + editor.value.substring(end);
        editor.selectionStart = editor.selectionEnd = start + res.length;
        editor.focus();
        updateStats();
    }

    function insertChar(char) {
        const editor = getEditor();
        const start = editor.selectionStart;
        editor.value = editor.value.substring(0, start) + char + editor.value.substring(editor.selectionEnd);
        editor.selectionStart = editor.selectionEnd = start + char.length;
        editor.focus();
        updateStats();
    }

    function autoEmojify() {
        const editor = getEditor();
        editor.value = editor.value.replace(/\\b(\\w+)\\b/g, (match) => {
            const lower = match.toLowerCase();
            return buzzwords[lower] ? `${match} ${buzzwords[lower]}` : match;
        });
        showToast("Magic Emojis Applied! ✨");
        updateStats();
    }
    
    function copyText() {
        const editor = getEditor();
        if(!editor.value) return;
        navigator.clipboard.writeText(editor.value).then(() => showToast("Copied to clipboard!"));
    }

    function showToast(msg) {
        const toast = document.getElementById('toast');
        toast.innerText = msg;
        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 2500);
    }
    
    function updateStats() {
        const val = getEditor().value;
        document.getElementById('charCount').innerText = val.length + " chars";
    }
""")

# --- 3. FASTHTML COMPONENTS ---

def Header():
    return Div(
        H1("LinkedIn Formatter ✨"),
        P("Convert GenAI text into elegant, formatted posts.", style="color: #666; font-size: 0.9rem; margin-top: 5px;"),
        cls="header"
    )

def ToolButton(label, onclick, title):
    # Using cls='tool-btn' to hook into our CSS
    return Button(label, onclick=onclick, title=title, cls="tool-btn", type="button")

def Toolbar():
    return Div(
        # Style Group
        Div(
            Span("Styles", cls="label"),
            ToolButton(B("B"), "applyFormat('boldSans')", "Bold"),
            ToolButton(I("I"), "applyFormat('italicSans')", "Italic"),
            ToolButton(U("U"), "applyFormat('underline')", "Underline"),
            cls="toolbar-group"
        ),
        # Magic Group
        Div(
            Span("Magic", cls="label"),
            ToolButton("✨ Auto-Emojify", "autoEmojify()", "Add Emojis"),
            ToolButton("• Bullet", "insertChar('• ')", "Bullet Point"),
            ToolButton("🚀 Rocket", "insertChar('🚀 ')", "Rocket"),
            cls="toolbar-group",
            style="background: #fafafa;"
        )
    )

def AppFooter():
    return Div(
        Div(Span("0 chars", id="charCount"), cls="stats", style="color: #666; font-size: 0.85rem;"),
        Button("Copy for LinkedIn", onclick="copyText()", cls="btn-primary"),
        cls="footer"
    )

app, rt = fast_app(hdrs=[app_css])

@rt("/")
def get():
    return Titled("LinkedIn Formatter",
        Div(
            Header(),
            Toolbar(),
            Div(
                Textarea(
                    id="editor", 
                    placeholder="Paste your text here... Select text and click 'B' to bold.",
                    oninput="updateStats()"
                ),
                cls="editor-wrapper"
            ),
            AppFooter(),
            cls="app-container"
        ),
        Div(id="toast", cls="toast"),
        client_logic 
    )

serve()
