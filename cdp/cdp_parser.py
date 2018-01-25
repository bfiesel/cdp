from __future__ import print_function

import sys
import argparse
import abc
import json
import yaml
from six import with_metaclass

if sys.version_info[0] >= 3:
    import configparser
else:
    import ConfigParser as configparser


class CDPParser(argparse.ArgumentParser):
    def __init__(self, parameter_cls, *args, **kwargs):
        # conflict_handler='resolve' lets new args override older ones
        super(CDPParser, self).__init__(conflict_handler='resolve',
                                        *args, **kwargs)
        self.load_default_args()
        self.__parameter_cls = parameter_cls
        self.__args_namespace = None

    def parse_args(self, args=None, namespace=None):
        """
        Overwrites default ArgumentParser.parse_args().
        We need to save the command used to run the parser, which is args or sys.argv.
        This is because the command used is not always sys.argv.
        """
        self.cmd_used = sys.argv if not args else args
        return super(CDPParser, self).parse_args(args, namespace)

    def view_args(self):
        """Returns the args namespace"""
        self._parse_arguments()
        return self.__args_namespace

    def _is_arg_default_value(self, arg):
        """
        Look at the command used for this parser (ex: test.py -s something --s1 something1)
        and if arg wasn't used, then it's a default value.
        """
        # each cmdline_arg is either '-*' or '--*'.
        for cmdline_arg in self._option_string_actions:
            # self.cmd_used is like: ['something.py', '-p', 'test.py', '--s1', 'something']
            if arg == self._option_string_actions[cmdline_arg].dest and cmdline_arg in self.cmd_used:
                return False
        return True

    def _overwrite_parameters_with_cmdline_args(self, parameters):
        """
        Overwrite the parameters with the user's command line arguments.
        Case 1: No param in parameters, use what's in --param. Even if cmdline arg (--param) is a default argument.
        Case 2: When there's a param in parameters and --param is given, use cmdline arg, but only if it's NOT a default value.

        So the only use of the default in a cmdline arg is when there's nothing for it in parameters.
        """
        for arg_name, arg_value in vars(self.__args_namespace).items():
            # Case 1
            if not hasattr(parameters, arg_name):
                setattr(parameters, arg_name, arg_value)
            # Case 2
            if hasattr(parameters, arg_name) and not self._is_arg_default_value(arg_name):
                setattr(parameters, arg_name, arg_value)

    def _parse_arguments(self):
        """Parse the command line arguments while checking for the user's arguments"""
        if self.__args_namespace is None:
            self.__args_namespace = self.parse_args()            
            if self.__args_namespace.parameters is None and self.__args_namespace.other_parameters is None:
                print('You must have either the -p or -d arguments.')
                self.print_help()
                sys.exit()

    def get_orig_parameters(self, default_vars=True, check_values=True):
        """Returns the parameters created by -p. If -p wasn't used, returns None."""
        parameter = self.__parameter_cls()

        self._parse_arguments()
        
        if self.__args_namespace.parameters is None:
            return None

        if not default_vars:  # remove all of the variables
            parameter.__dict__.clear()

        #if self.__args_namespace.parameters is not None:
        parameter.load_parameter_from_py(
            self.__args_namespace.parameters)

        self._overwrite_parameters_with_cmdline_args(parameter)

        if check_values:
            parameter.check_values()

        return parameter

    def get_parameters_from_json(self, json_file, default_vars=True, check_values=True):
        """Given a json file, return the parameters from it."""
        with open(json_file) as f:
            json_data = json.loads(f.read())

        parameters = []
        for key in json_data:
            for single_run in json_data[key]:
                p = self.__parameter_cls()

                if not default_vars:  # remove all of the variables
                    p.__dict__.clear()

                for attr_name in single_run:
                    setattr(p, attr_name, single_run[attr_name])

                self._overwrite_parameters_with_cmdline_args(p)

                if check_values:
                    p.check_values()

                parameters.append(p)

        return parameters

    def get_parameters_from_cfg(self, json_file, default_vars=True, check_values=True):
        """Given a cfg file, return the parameters from it."""
        parameters = []

        config = configparser.ConfigParser()
        config.read(json_file)

        for section in config.sections():
            p = self.__parameter_cls()

            if not default_vars:  # remove all of the variables
                p.__dict__.clear()

            for k, v in config.items(section):
                v = yaml.safe_load(v)
                setattr(p, k, v)

            self._overwrite_parameters_with_cmdline_args(p)

            if check_values:
                p.check_values()

            parameters.append(p)

        return parameters

    def get_other_parameters(self, files_to_open=[], default_vars=True, check_values=True):
        """Returns the parameters created by -d, If files_to_open is defined, 
        then use the path specified instead of -d"""
        parameters = []
    
        self._parse_arguments()

        if files_to_open == []:
            files_to_open = self.__args_namespace.other_parameters

        if files_to_open is not None:
            for diags_file in files_to_open:
                if '.json' in diags_file:
                    params = self.get_parameters_from_json(diags_file, default_vars, check_values)
                elif '.cfg' in diags_file:
                    params = self.get_parameters_from_cfg(diags_file, default_vars, check_values)
                else:
                    raise RuntimeError('The parameters input file must be either a .json or .cfg file')

                for p in params:
                    parameters.append(p)

        return parameters

    def combine_orig_and_other_params(self, orig_parameters, other_parameters, vars_to_ignore=[]):
        """Combine orig_parameters with all of the other_parameters, while ignoring vars_to_ignore"""
        for parameters in other_parameters:
            for var in orig_parameters.__dict__:
                if var not in vars_to_ignore:
                    parameters.__dict__[var] = orig_parameters.__dict__[var]

    def get_parameters(self, orig_parameters=None, other_parameters=[], vars_to_ignore=[], *args, **kwargs):
        """Get the parameters based on the command line arguments and return a list of them."""
        if orig_parameters is None:
            orig_parameters = self.get_orig_parameters(*args, **kwargs)
        if other_parameters == []:
            other_parameters = self.get_other_parameters(*args, **kwargs)            

        if orig_parameters is not None and other_parameters == []:  # only -p
            return [orig_parameters]
        elif orig_parameters is None and other_parameters != []:  # only -d
            return other_parameters
        elif orig_parameters is not None and other_parameters != []:  # used -p and -d
            self.combine_orig_and_other_params(orig_parameters, other_parameters, vars_to_ignore)
            return other_parameters
        else:
            raise RuntimeError("You ran your script without a '-p' or '-d' argument.")

    def get_parameter(self, warning=False, *args, **kwargs):
        """Return the first Parameter in the list of Parameters."""
        if warning:
            print('Deprecation warning: Use get_parameters() instead, which returns a list of Parameters.')
        return self.get_parameters(*args, **kwargs)[0]

    def load_default_args(self):
        """Load the default arguments for the parser."""
        self.add_argument(
            '-p', '--parameters',
            type=str,
            dest='parameters',
            help='Path to the user-defined parameter file',
            required=False)
        self.add_argument(
            '-d', '--diags',
            type=str,
            nargs='+',
            dest='other_parameters',
            default=[],
            help='Path to the other user-defined parameter file',
            required=False)
        self.add_argument(
            '-n', '--num_workers',
            type=int,
            dest='num_workers',
            help='Number of workers, used when running with multiprocessing or distributedly',
            required=False)
        self.add_argument(
            '--scheduler_addr',
            type=str,
            dest='scheduler_addr',
            help='Address of the scheduler in the form of IP_ADDRESS:PORT. Used when running distributedly',
            required=False)

    def add_args_and_values(self, arg_list):
        """Used for testing. Can test args input as if they
        were inputted from the command line."""
        self.__args_namespace = self.parse_args(arg_list)
