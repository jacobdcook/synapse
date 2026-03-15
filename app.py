from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from database import create_tables, save_paste, get_paste, list_pastes, delete_paste, get_paste_count
from datetime import datetime

app = Flask(__name__)

# Configuration
MAX_PASTE_SIZE = 100 * 1024  # 100KB
SUPPORTED_LANGUAGES = [
    ('python', 'Python'),
    ('javascript', 'JavaScript'),
    ('html', 'HTML'),
    ('css', 'CSS'),
    ('sql', 'SQL'),
    ('bash', 'Bash'),
    ('json', 'JSON'),
    ('plain', 'Plain Text')
]

# Initialize database on startup
create_tables()


@app.route('/')
def index():
    """Homepage with paste creation form."""
    return render_template('index.html', languages=SUPPORTED_LANGUAGES)


@app.route('/paste', methods=['POST'])
def create_paste():
    """Create a new paste."""
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '')
    language = request.form.get('language', 'plain')
    
    # Validation
    if not content:
        return render_template('index.html', 
                             languages=SUPPORTED_LANGUAGES,
                             error='Content is required')
    
    if len(content) > MAX_PASTE_SIZE:
        return render_template('index.html',
                             languages=SUPPORTED_LANGUAGES,
                             error=f'Content too large (max {MAX_PASTE_SIZE // 1024}KB)')
    
    if not title:
        title = 'Untitled Paste'
    
    # Save paste
    paste_id = save_paste(title, content, language)
    return redirect(url_for('view_paste', paste_id=paste_id))


@app.route('/p/<paste_id>')
def view_paste(paste_id):
    """View a single paste with syntax highlighting."""
    paste = get_paste(paste_id)
    if not paste:
        abort(404)
    return render_template('view.html', paste=paste)


@app.route('/list')
def list_pastes_view():
    """List recent pastes."""
    pastes = list_pastes(limit=50)
    return render_template('list.html', pastes=pastes)


@app.route('/api/pastes', methods=['GET'])
def api_list_pastes():
    """API endpoint for listing recent pastes (JSON)."""
    pastes = list_pastes(limit=50)
    return jsonify({
        'pastes': pastes,
        'count': len(pastes)
    })


@app.route('/api/paste/<paste_id>', methods=['DELETE'])
def api_delete_paste(paste_id):
    """API endpoint for deleting a paste."""
    deleted = delete_paste(paste_id)
    if deleted:
        return jsonify({'message': 'Paste deleted', 'id': paste_id}), 200
    return jsonify({'error': 'Paste not found'}), 404


@app.errorhandler(404)
def not_found(e):
    """Custom 404 error page."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Custom 500 error page."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
