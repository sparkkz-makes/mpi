from setuptools import find_packages, setup

package_name = 'mentorpi_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/teleop_joy_params.yaml']),
        ('share/' + package_name + '/launch', ['launch/gamepad_teleop.launch.py']),
    ],
    install_requires=['setuptools', 'loguru'],
    zip_safe=True,
    maintainer='stu',
    maintainer_email='stuart.parkinson.nz@gmail.com',
    description='ROS2 driver for MentorPi RRC Lite controller board',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'buzzer_node = mentorpi_driver.buzzer_node:main',
            'serial_driver = mentorpi_driver.serial_driver:main',
            'motor_driver = mentorpi_driver.motor_driver:main',
            'joy_inspector = mentorpi_driver.joy_inspector:main',
        ],
    },
)