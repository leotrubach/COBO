from __future__ import print_function
import argparse
import logging
import os
import os.path
import subprocess
import sys

import scipy.optimize


class TunerException(Exception):
    pass


class Tuner(object):
    def __init__(self, engine_path, depth, multipv=1, hash=16):
        self.depth = depth
        self.multipv = multipv
        self.hash = hash
        self.engine_path = engine_path
        self.engine_running = False
        self.pars = self._get_pars()
        self.param_names = [p[0] for p in self.pars]

    def _start_engine(self):
        self._sf = subprocess.Popen(
            os.path.join(os.getcwd(), self.engine_path),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1)
        self.engine_running = True

    def _stop_engine(self):
        self.engine.kill()
        self.engine_running = False

    @property
    def engine(self):
        if not self.engine_running:
            self._start_engine()
        return self._sf

    def _get_pars(self):
        self.engine.stdin.write('isready\n')
        pars = []
        while True:
            outline = self.engine.stdout.readline().rstrip()
            logging.debug(outline)
            if outline == 'readyok':
                break
            if not outline.startswith('Stockfish'):
                pars.append(outline.split(','))
        return pars

    def _parse_benchmark(self):
        correlation, depth = None, None
        output_lines = []
        while True:
            outline = self.engine.stdout.readline().rstrip()
            output_lines.append(outline)
            if outline.startswith('Search/eval correlation'):
                correlation = float(outline.split()[2])
            if outline.startswith('info depth'):
                depth = int(outline.split()[2])

            if outline.startswith('Total time'):
                if correlation and depth:
                    return correlation, depth
                else:
                    logging.error('Could not parse benchmark output:\n%s', '\n'.join(output_lines))
                    raise TunerException('Benchmark parse error')

    def run_benchmarks(self):
        for p in self.pars:
            logging.debug('%s %s', p[0], p[1])
        self.engine.stdin.write('setoption name multipv value {}\n'.format(self.multipv))
        self.engine.stdin.write('setoption name Hash value {}\n'.format(self.hash))

        for par in self.pars:
            cmd = 'setoption name {par[0]} value {par[1]}\n'.format(par=par)
            self.engine.stdin.write(cmd)

        self.engine.stdin.write('go depth {}\n'.format(self.depth))
        self.engine.stdin.write('bench 16 1 {} balancedMiddlegames.epd\n'.format(self.depth - 10))
        self.engine.stdin.write('bench 16 1 {} balancedEndgames.epd\n'.format(self.depth - 13))

        benchmark_results = [self._parse_benchmark() for _ in range(2)]
        for br in benchmark_results:
            logging.info('Search/eval correlation {} depth {}', br[0], br[1])
        result = benchmark_results[-1][0]

        logging.debug('Result: %s', result)
        self._stop_engine()
        return result

    def apply_pars(self, pars_array):
        for n, par in enumerate(pars_array):
            self.pars[n][1] = int(round(float(pars_array[n])))

    def pars2array(self):
        return [par[1] for par in self.pars]

    def get_bounds(self):
        return [(p[2], p[3]) for p in self.pars]

    def fitness(self, pars_array=None):
        if pars_array:
            self.apply_pars(pars_array)
        return -self.run_benchmarks()

    def print_status_msg(self, xk, convergence=0):
        for name, p in zip(self.param_names, xk):
            print('{} {}'.format(name, p))
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', help='Engine executable')
    parser.add_argument('depth', type=int, help='Search depth')
    parser.add_argument('--popsize', type=int)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(message)s', level='DEBUG')
    else:
        logging.basicConfig(format='%(message)s', level='INFO')
    t = Tuner(args.engine, args.depth)

    if not t.pars:
        logging.warning('No parameters to tune')
        exit(1)

    f = t.fitness()
    logging.info('Reference correlation: {}', f)

    optimizer_kwargs = {
        'disp': True,
        'callback': t.print_status_msg
    }
    if args.popsize:
        optimizer_kwargs['popsize'] = args.popsize

    res = scipy.optimize.differential_evolution(t.fitness, t.get_bounds(), **optimizer_kwargs)
    t.print_status_msg(res.x)
    print('Search/eval correlation: {}'.format(-res.fun))
