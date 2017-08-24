# -*- coding: utf-8 -*-
def register_task():
    tasks = {}

    def register(function):
        tasks[function.__name__] = function
        return function

    register.all = tasks
    return register

task = register_task()
