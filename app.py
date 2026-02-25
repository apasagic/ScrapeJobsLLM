# app.py
from flask import Flask, request, render_template
from main import process_text

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        user_input = request.form['user_input']
        result = process_text(user_input)
    return render_template('form.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)