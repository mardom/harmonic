import numpy as np
import sys
sys.path.append(".")
import harmonic as hm
import emcee
import scipy.special as sp
import time 
import matplotlib.pyplot as plt
import utils
import gc 

# Setup Logging config
hm.logs.setup_logging()


def ln_analytic_evidence(ndim, cov):
    """
    Compute analytic ln_e evidence.
    Args: 
        - ndim: 
            Dimensionality of the multivariate Gaussian posterior
        - cov
            Covariance matrix dimension nxn.           
    Returns:
        - double: 
            Value of posterior at x.
    """
    ln_norm_lik = -0.5*ndim*np.log(2*np.pi)-0.5*np.log(np.linalg.det(cov))   
    return -ln_norm_lik

def ln_Posterior(x, inv_cov):
    """
    Compute log_e of n dimensional multivariate gaussian 
    Args: 
        - x: 
            Position at which to evaluate prior.         
    Returns:
        - double: 
            Value of posterior at x.
    """
    return -np.dot(x,np.dot(inv_cov,x))/2.0   

def init_cov(ndim): 
    """
    Initialise random diagonal covariance matrix.
    Args: 
        - ndim: 
            Dimension of Gaussian.        
    Returns:
        - cov: 
            Covariance matrix of shape (ndim,ndim).
    """

    cov = np.zeros((ndim,ndim))
    diag_cov = np.ones(ndim)
    np.fill_diagonal(cov, diag_cov)
    
    return cov


def run_example(ndim=2, nchains=100, samples_per_chain=1000, 
                nburn=500, chain_iterations=1, verbose=True, 
                plot_corner=False, plot_surface=False):
    """
    Run nD Gaussian example with generalized covariance matrix.
    Args: 
        - ndim: 
            Dimension of multivariate Gaussian.
        - nchains: 
            Number of chains.
        - samples_per_chain: 
            Number of samples per chain.
        - nburn: 
            Number of burn in samples.
        - plot_corner: 
            Plot marginalised distributions if true.
        - plot_surface: 
            Plot surface and samples if true.
        - verbose: 
            If True then displalnprob intermediate results.
        
    Returns:
        - None.
    """

    hm.logs.critical_log('nD Guassian example')
    hm.logs.critical_log('Dimensionality = {}'.format(ndim))
    hm.logs.debug_log('---------------------------------')
    savefigs = True
    plot_sample = False

    # ==========================================================================
    # Initialise covariance matrix.
    # ==========================================================================
    cov = init_cov(ndim)
    inv_cov = np.linalg.inv(cov)  
    hm.logs.debug_log('Covariance matrix diagonal entries = \n{}'
        .format(np.diagonal(cov)))
    hm.logs.debug_log('---------------------------------')

    # ==========================================================================
    # Compute analytic log-evidence for comparison
    # ==========================================================================
    ln_rho = -ln_analytic_evidence(ndim, cov)
    hm.logs.critical_log('Ln Inverse Analytic evidence = {}'.format(ln_rho))
    hm.logs.debug_log('---------------------------------')

    # ==========================================================================
    # Set up hyper-parameters for AI model
    # ==========================================================================

    max_r_prob = np.sqrt(ndim-1)
    hm.logs.debug_log('max_r_prob = {}'.format(max_r_prob))
    domains_sphere = [max_r_prob*np.array([1E0,2E1])]
    hyper_parameters_sphere = [None]

    # ==========================================================================
    # Begin primary iterations
    # ==========================================================================

    # Run multiple realisations.
    n_realisations = 1
    evidence_inv_summary = np.zeros((n_realisations,3))
    # Start timer.
    clock = time.clock()
    for i_realisation in range(n_realisations):

        if n_realisations > 0:
            hm.logs.critical_log('Realisation = {}/{}'
                .format(i_realisation, n_realisations))

        # ======================================================================
        # Recover a set of MCMC samples from the posterior 
        # ======================================================================

        burn_iterations = 50
        pos = np.random.rand(ndim * nchains).reshape((nchains, ndim))
        rstate = np.random.get_state() # Set random state to be repeatable.

        for burn_iteration in range(burn_iterations+1):
            hm.logs.debug_log('Run burn sampling for burning subiteration {}...'.format(
                    burn_iteration+1))
            hm.logs.debug_log('---------------------------------')
            # Clear memory
            if burn_iteration > 0:
                del sampler, prob
                gc.collect()
            # Run the emcee sampler from previous endpoint
            sampler = emcee.EnsembleSampler(nchains, ndim, ln_Posterior, \
                                        args=[inv_cov])
            if burn_iteration < burn_iterations:
                (pos, prob, rstate) = sampler.run_mcmc(pos, nburn/burn_iterations, \
                                              rstate0=rstate) 
            else:
                (pos, prob, rstate) = sampler.run_mcmc(pos, samples_per_chain-nburn, \
                                              rstate0=rstate) 
        samples = np.ascontiguousarray(sampler.chain[:,:,:])
        lnprob = np.ascontiguousarray(sampler.lnprobability[:,:])

        # ======================================================================
        # Configure chains
        # ======================================================================
        chains = hm.Chains(ndim)
        chains.add_chains_3d(samples, lnprob)

        # ======================================================================
        # Train hyper-spherical model 
        # ======================================================================
        model = hm.model.HyperSphere(ndim, domains_sphere)
        fit_success, objective = model.fit(chains.samples,\
                                           chains.ln_posterior) 
        hm.logs.debug_log('Fit success = {}'.format(fit_success))    
        hm.logs.debug_log('Objective = {}'.format(objective))    
        hm.logs.debug_log('---------------------------------')

        # ======================================================================

        # Compute ln evidence by iteratively adding chains
        # ======================================================================
        # Instantiate the evidence class
        hm.logs.critical_log('Compute evidence...')
        cal_ev = hm.Evidence(chains.nchains, model)

        for chain_iteration in range(chain_iterations):
            hm.logs.debug_log('Run sampling for chain subiteration {}...'.format(
                    chain_iteration+1))
            hm.logs.debug_log('---------------------------------')
            # Clear memory
            del chains, samples, lnprob, sampler, prob
            gc.collect()
            # Run the emcee sampler from previous endpoint
            sampler = emcee.EnsembleSampler(nchains, ndim, ln_Posterior, \
                                        args=[inv_cov])
            (pos, prob, rstate) = sampler.run_mcmc(pos, (samples_per_chain-nburn)/10, \
                                              rstate0=rstate) 
            samples = np.ascontiguousarray(sampler.chain[:,:,:])
            lnprob = np.ascontiguousarray(sampler.lnprobability[:,:])
            # Create a new chains class and add the new chains
            chains = hm.Chains(ndim)
            chains.add_chains_3d(samples, lnprob)

            # Add these new chains to running sum
            cal_ev.add_chains(chains)

        ln_evidence, ln_evidence_std = cal_ev.compute_ln_evidence()

        cal_ev.serialize(".test.gaussian_dim_{}.dat".format(ndim))

        # ======================================================================
        # Display logarithmic inverse evidence computation results.
        # ======================================================================
        hm.logs.debug_log('---------------------------------')
        hm.logs.debug_log('Ln Inv Evidence: analytic = {}, estimate = {}'
            .format(ln_rho, np.log(cal_ev.evidence_inv)))
        hm.logs.critical_log('Ln Inv Evidence: \
                          100 * |analytic - estimate| / |analytic| = {}%'
            .format(100.0 * np.abs( (np.log(cal_ev.evidence_inv) - ln_rho) \
                                                                 / ln_rho ))) 
        # ======================================================================
        # Display inverse evidence computation results.
        # ======================================================================
        hm.logs.debug_log('---------------------------------')
        hm.logs.debug_log('Inv Evidence: analytic = {}, estimate = {}'
            .format(np.exp(ln_rho), cal_ev.evidence_inv))
        hm.logs.debug_log('Inv Evidence: std = {}, std / estimate = {}'
            .format(np.sqrt(cal_ev.evidence_inv_var), \
                    np.sqrt(cal_ev.evidence_inv_var)/cal_ev.evidence_inv))
        hm.logs.critical_log("Inv Evidence: \
                          100 * |analytic - estimate| / estimate = {}%"
            .format(100.0 * np.abs( np.exp(ln_rho) - cal_ev.evidence_inv ) \
                                                   / cal_ev.evidence_inv ) )
        # ======================================================================
        # Display more technical details for ln evidence.
        # ======================================================================
        hm.logs.debug_log('---------------------------------')
        hm.logs.debug_log('lnargmax = {}, lnargmin = {}'
            .format(cal_ev.lnargmax, cal_ev.lnargmin))
        hm.logs.debug_log('lnprobmax = {}, lnprobmin = {}'
            .format(cal_ev.lnprobmax, cal_ev.lnprobmin))
        hm.logs.debug_log('lnpredictmax = {}, lnpredictmin = {}'
            .format(cal_ev.lnpredictmax, cal_ev.lnpredictmin))
        hm.logs.debug_log('---------------------------------')
        hm.logs.debug_log('shift = {}, shift setting = {}'
            .format(cal_ev.shift_value, cal_ev.shift))
        hm.logs.debug_log('running sum total = {}'
            .format(sum(cal_ev.running_sum)))
        hm.logs.debug_log('running_sum = \n{}'
            .format(cal_ev.running_sum))
        hm.logs.debug_log('nsamples_per_chain = \n{}'
            .format(cal_ev.nsamples_per_chain))
        hm.logs.debug_log('nsamples_eff_per_chain = \n{}'
            .format(cal_ev.nsamples_eff_per_chain))
        hm.logs.debug_log('===============================')

        # ======================================================================
        # Create corner/triangle plot.
        # ======================================================================
        created_plots = False
        if plot_corner and i_realisation == 0:
            
            utils.plot_corner(samples.reshape((-1, ndim)))

            if savefigs:
                plt.savefig('examples/plots/nD_gaussian_corner.png',
                            bbox_inches='tight')

            plt.show(block=False)
            created_plots = True

        evidence_inv_summary[i_realisation,0] = cal_ev.evidence_inv
        evidence_inv_summary[i_realisation,1] = cal_ev.evidence_inv_var
        evidence_inv_summary[i_realisation,2] = cal_ev.evidence_inv_var_var


    clock = time.clock() - clock
    hm.logs.critical_log('Execution_time = {}s'.format(clock))

    if n_realisations > 1:
        np.savetxt("examples/data/nD_gaussian_evidence_inv" +
                   "_realisations.dat",
                   evidence_inv_summary)
        evidence_inv_analytic_summary = np.zeros(1)
        evidence_inv_analytic_summary[0] = np.exp(ln_rho)
        np.savetxt("examples/data/nD_gaussian_evidence_inv" +
                   "_analytic.dat",
                   evidence_inv_analytic_summary)

    if created_plots:
        input("\nPress Enter to continue...")
    
    return samples



if __name__ == '__main__':
    
    # Define parameters.
    ndim = 32
    nchains = 2*ndim
<<<<<<< HEAD
    samples_per_chain = 10000
    nburn = 7000
    chain_iterations = 50
    np.random.seed(2)
=======
    samples_per_chain = 44000
    nburn = 40000
    chain_iterations = 600
    np.random.seed(1)
>>>>>>> stash current version
    
    # Run example.
    run_example(ndim, nchains, samples_per_chain, nburn, chain_iterations,
                plot_corner=False, plot_surface=False, verbose=False)


