#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright 2017 National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and 
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain 
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

import logging

import pyutilib.services as services

from pyutilib.common import ApplicationError
from pyutilib.misc import Bunch, Options
from pyutilib.services.TempfileManager import create_tempfile

from pyomo.util.plugin import alias
from pyomo.opt import SolverResults
from pyomo.opt.base import OptSolver, SolverFactory, ProblemFormat, ResultsFormat
from pyomo.opt.solver import SystemCallSolver
from pyomo.opt.base.solvers import _extract_version
from pyomo.solvers.mockmip import MockMIP

from six import iteritems, string_types

logger = logging.getLogger('pyomo.solvers')

_mipcl_version = None

def configure_mipcl():
    global _mipcl_version
    if _mipcl_version is not None:
        return
    _mipcl_version = _extract_version('') #TODO
    if services.registered_executable('mps_mipcl') is None:
        return
    
class MIPCL(OptSolver):
    """The MIPCL LP/MIP solver"""
    
    alias('mipcl', doc='The MIPCL LP/MIP solver')
    
    def __new__(cls, *args, **kwds):
        configure_mipcl()
        try:
            mode = kwds['solver_io']
            if mode is None:
                mode = 'mps'
            del kwds['solver_io']
        except KeyError:
            mode = 'mps'
        if mode  == 'mps':
            opt = SolverFactory('_mipcl_shell', **kwds)
            opt.set_problem_format(ProblemFormat.mps)
            return opt
        if mode  == 'mod':
            opt = SolverFactory('_mipcl_shell', **kwds)
            opt.set_problem_format(ProblemFormat.cpxlp)
            return opt
        if mode == 'os':
            opt = SolverFactory('_ossolver', **kwds)
        else:
            logger.error('Unknown IO type: %s' % mode)
            return
        opt.set_options('solver=mps_mipcl')
        return opt

class MIPCLSHELL(SystemCallSolver):
    """Shell interface to the MIPCL LP/MIP solver"""
    
    alias('_mipcl_shell', doc='Shell interface to the MIPCL LP/MIP solver')
    
    def __init__(self, **kwds):
        kwds['type'] = 'mipcl'
        SystemCallSolver.__init__(self, **kwds)
        
        self._valid_problem_formats = [ProblemFormat.mps, ProblemFormat.mod]
        self._valid_result_formats = {ProblemFormat.mps: ResultsFormat.soln,
                                      ProblemFormat.mod: ResultsFormat.soln}
        self.set_problem_format(ProblemFormat.mps)
        
        self._capabilities = Options()
        self._capabilities.linear = True
        self._capabilities.integer = True
        
    def _default_results_format(self, prob_format):
        return ResultsFormat.soln
    
    def _default_executable(self):
        executable = services.registered_executable('mps_mipcl')
        if executable is None:
            logger.warning("Could not locate the 'mps_mipcl' executable,"
                    " which is required for solver '%s'" % self.name)
            self.enable = False
            return None
        return executable.get_path()
    
    def _get_version(self):
        """Returns a tuple describing the solver executable version."""
        if _mipcl_version is None:
            return _extract_version('')
        return _mipcl_version

    def create_command_line(self, executable, problem_files):
        if self._log_file is None:
            self._log_file = create_tempfile(suffix='.mipcl.log')
        
        self._soln_file = None
        
        cmd = [executable]
        if self._timer:
            cmd.insert(0, self._timer)
        for k,v in iteritems(self.options):
            if v is None or (isinstance(v, string_types) and v.strip() == ''):
                cmd.append("--%s" % k)
            else:
                cmd.extend(["--%s" % k, str(v)])

        if self._timelimit is not None and self._timelimit > 0.0:
            cmd.extend(['-time', str(self._timelimit)])

        return Bunch(cmd=cmd, log_file=self._log_file, env=None)
    
    def process_logfile(self):
        """Process logfile"""
        results = SolverResults()
        #TODO
        return results
    
    def process_soln_file(self, results):
        pass

class MockMIPCL(MIPCLSHELL, MockMIP):
    """A Mock MIPCL solver used for testing"""
    
    alias('_mock_mipcl')
    
    def __init__(self, **kwds):
        try:
            MIPCLSHELL.__init__(self, **kwds)
        except ApplicationError:
            pass
        MockMIP.__init__(self, "mipcl")

    def available(self, exception_flag=True):
        return MIPCLSHELL.available(self, exception_flag)

    def create_command_line(self, executable, problem_files):
        command = MIPCLSHELL.create_command_line(self, executable, problem_files)
        MockMIP.create_command_line(self, executable, problem_files)
        return command

    def executable(self):
        return MockMIP.executable(self)

    def _execute_command(self, cmd):
        return MockMIP._execute_command(self, cmd)

    def _convert_problem(self, args, pformat, valid_pformats):
        if pformat in [ProblemFormat.mps, ProblemFormat.mod]:
            return (args, pformat, None)
        else:
            return (args, ProblemFormat.mps, None)

services.register_executable(name="mps_mipcl")