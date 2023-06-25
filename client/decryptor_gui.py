import tkinter as tk
import os
import base64
from Crypto.Cipher import AES
from tkinter.messagebox import askyesno

root = tk.Tk()
root.geometry('400x525')
root.title('Decryptor')
root.resizable(width=False, height=False)

LABEL_FONT = ('Arial', 18)

# root folder path
path_label = tk.Label(root, text='Root Folder Path', font=LABEL_FONT)
path_label.pack(pady=(10, 0))
path_textbox = tk.Text(root, height=2, width=24, font=LABEL_FONT)
path_textbox.pack(pady=(0,10))

# encrypted file extension
file_ext_label = tk.Label(root, text='Encrypted File Extension', font=LABEL_FONT)
file_ext_label.pack()
file_ext_textbox= tk.Text(root, height=2, width=24, font=LABEL_FONT)
file_ext_textbox.pack(pady=(0,10))

# b64 str init vector
init_vec_label = tk.Label(root, text='Initialization Vector', font=LABEL_FONT)
init_vec_label.pack()
init_vec_textbox = tk.Text(root, height=2, width=24, font=LABEL_FONT)
init_vec_textbox.pack(pady=(0,10))

# b64 str unencrypted AES key
key_label = tk.Label(root, text='Key', font=LABEL_FONT)
key_label.pack()
key_textbox = tk.Text(root, height=2, width=24, font=LABEL_FONT)
key_textbox.pack(pady=(0, 25))

# button action
def on_press():
    answer = askyesno('Start Decryption', 'Are you 100% sure you have entered all of the correct info in the fields?')
    if answer is False:
        return
    global path_textbox, file_ext_textbox
    global init_vec_textbox, key_textbox
    top_dir = path_textbox.get(1.0, tk.END).strip()
    encrypted_file_ext = file_ext_textbox.get(1.0, tk.END).strip()
    decoded_key: bytes = base64.b64decode(key_textbox.get(1.0, tk.END).encode('utf-8')).strip()
    decoded_init_vec: bytes = base64.b64decode(init_vec_textbox.get(1.0, tk.END).encode('utf-8')).strip()
    for root, dirs, files in os.walk(top_dir):
        for filename in files:
            if os.path.splitext(filename)[-1] == encrypted_file_ext:
                # decrypt file
                cipher = AES.new(decoded_key, AES.MODE_CBC, decoded_init_vec)
                full_filepath = os.path.join(root, filename)
                with open(full_filepath, 'rb') as f:
                    file_contents = f.read()
                with open(os.path.join(full_filepath), 'wb') as f:
                    f.write(cipher.decrypt(file_contents))
                os.rename(full_filepath, os.path.splitext(full_filepath)[0])

# start button
start_btn = tk.Button(root, text="START", font=LABEL_FONT, command=on_press, padx=120, pady=10)
start_btn.pack()

root.mainloop()
