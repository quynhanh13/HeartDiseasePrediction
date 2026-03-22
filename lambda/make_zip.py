import os
import zipfile

src_dir = 'deployment_linux'
out_zip = 'lambda-deployment.zip'

if os.path.exists(out_zip):
    os.remove(out_zip)

with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.pyc'):
                continue
            full_path = os.path.join(root, f)
            arc_path = os.path.relpath(full_path, src_dir)
            zf.write(full_path, arc_path)

print(f'Created {out_zip} ({os.path.getsize(out_zip)} bytes)')
