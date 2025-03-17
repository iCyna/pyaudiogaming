import json
import hashlib
import pickle
import os
import shutil
import base64
from cryptography.fernet import Fernet
import io

class File:
	def __init__(self, password: str, encode: bool = False):
		self.key = self.generate_key(password)
		self.cipher = self.dokey(self.key)
		self.file_obj = None
		self.encode = encode

	@staticmethod
	def generate_key(password: str) -> bytes:
		"""
		Tạo key từ mật khẩu bằng cách băm SHA-256.
		"""
		return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

	@staticmethod
	def dokey(key: bytes) -> Fernet:
		"""
		Tạo đối tượng Fernet từ key.
		"""
		return Fernet(key)

	def open(self, file_path, mode):
		self.file_obj = open(file_path, mode)

	def close(self):
		if self.file_obj:
			self.file_obj.close()
			self.file_obj = None

	def save(self, data, file_path, mode="w+", type=""):
		if type == "json":
			data = json.dumps(data)
		elif type == "pickle":
			data = pickle.dumps(data)
		elif type == "txt":
			data = str(data)
		if self.encode:
			data = self.cipher.encrypt(data.encode('utf-8'))
		with open(file_path, mode) as file:
			file.write(data)

	def load(self, file_path: str, mode="r+", type: str = ""):
		with open(file_path, mode) as file:
			data = file.read()
		if self.encode: data = self.cipher.decrypt(data).decode('utf-8')
		if type == "json":
			return json.loads(data)
		elif type == "pickle":
			return pickle.loads(data)
		return data

	def remove(self, file_path: str):
		if os.path.exists(file_path):
			return os.remove(file_path)

	def create(self, file_path: str):
		with open(file_path, 'w'): pass

	def check(self, file_path: str) -> bool:
		return os.path.exists(file_path)

	def replace(self, old_file, new_file):
		self.delete_file(old_file)
		shutil.move(new_file, old_file)

	def copy(self, src: str, dest: str):
		return shutil.copy(src, dest)

	def move(self, src, dest):
		return shutil.move(src, dest)
	# end class