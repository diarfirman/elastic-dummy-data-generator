import subprocess
import sys
from flask import Flask, render_template, request, stream_with_context, Response

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', request=request)

@app.route('/start_indexing', methods=['POST'])
def start_indexing():
    es_host = request.form.get('es_host')
    es_username = request.form.get('es_username')
    es_password = request.form.get('es_password')
    target_index = request.form.get('target_index')
    total_size_mb = request.form.get('total_size_mb')
    data_type = request.form.get('data_type')

    # Validasi input
    if not all([es_host, es_username, es_password, target_index, total_size_mb, data_type]):
        return Response("Error: All fields are required.\n", mimetype='text/plain')

    try:
        total_size_mb = int(total_size_mb)
        if total_size_mb <= 0:
            return Response("Error: Total Data Size (MB) must be a positive integer.\n", mimetype='text/plain')
    except ValueError:
        return Response("Error: Total Data Size (MB) must be an integer.\n", mimetype='text/plain')

    def generate():
        yield "INFO: Starting data generation process...\n"
        try:
            # Panggil script_executor.py sebagai subprocess
            process = subprocess.Popen(
                [
                    sys.executable,
                    'script_executor.py',
                    es_host,
                    es_username,
                    es_password,
                    target_index,
                    str(total_size_mb),
                    data_type
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Stream log baris per baris
            for line in iter(process.stdout.readline, ''):
                yield line

            process.wait()

            if process.returncode != 0:
                yield f"ERROR: Script exited with code {process.returncode}\n"
            else:
                yield "SUCCESS: Script executed successfully.\n"

        except FileNotFoundError:
            yield "ERROR: script_executor.py not found.\n"
        except Exception as e:
            yield f"ERROR: {str(e)}\n"

    return Response(stream_with_context(generate()), mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)
