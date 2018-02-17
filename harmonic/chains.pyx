import numpy as np
cimport numpy as np
import copy

class Chains:
    """Class to store samples from multiple MCMC chains.    
    """
        
    def __init__(self, int ndim):   
        """Construct empty Chains for parameter space of dimension ndim.
        
        Constructor simply sets ndim.  Chain sampeles are added by the
        add_chain* methods since we want to support setting up data for chains
        from different input data formats (e.g. data from a single chain or
        multiple chains at once).
        
        Args:
            ndim: Dimension of the parameter space.
        """    
        
        if ndim < 1:
            raise ValueError("ndim must be greater than 0")
        self.nchains = 0        
        self.start_indices = [0]  # stores start index of each chain
        self.ndim = ndim
        self.nsamples = 0        
        self.samples = np.empty((0, self.ndim))
        
    def add_chain(self, np.ndarray[double,ndim=2,mode="c"] samples not None):
        """Add a single chain.
        
        Args:
            samples: 2D numpy.ndarray containing the samples of a single chain 
                with shape (nsamples_in, ndim_in) and dtype double.
                
        Raises:
            TypeError: Raised when ndim of new chain does not match previous 
                chains.
        """
                        
        nsamples_in = samples.shape[0]
        ndim_in = samples.shape[1]
        
        # Check new chain has correct ndim.
        if ndim_in != self.ndim:            
            raise TypeError("ndim of new chain does not match previous chains")
        
        self.samples = np.concatenate((self.samples, samples))
        self.nsamples += nsamples_in                
        self.start_indices.append(self.nsamples)
        self.nchains += 1
        
        return
        
    def add_chains_2d(self, np.ndarray[double,ndim=2,mode="c"] samples not None,
                      int nchains_in):                
        """Add multiple chains stored in a concatenated numpy.ndarray, assuming
        all the chains are of the same length.

        Args:
            samples: 2D numpy.ndarray containing the samples with shape 
                (nsamples_in * nchains_in, ndim) and dtype double.
            nchains_in: int specifying the number of chains.
        
        Raises:
            ValueError: Raised when number of samples is not multiple of the   
                number of chains.
            TypeError: Raised when ndim of new chains does not match previous 
                chains.
        """

        if (samples.shape[0] % nchains_in) != 0:
            raise ValueError("The number of samples is not a multiple of the "
                + "number of chains")

        nsamples_in = samples.shape[0]
        ndim_in = samples.shape[1]

        # Check new chain has correct ndim.
        if ndim_in != self.ndim:            
            raise TypeError("ndim of new chain does not match previous chains")

        cdef int i_chain, samples_per_chain = nsamples_in/nchains_in
        for i_chain in range(nchains_in):
            self.add_chain(samples[i_chain*samples_per_chain:
                                   (i_chain+1)*samples_per_chain,:])

        return

    def add_chains_3d(self, 
                      np.ndarray[double,ndim=3,mode="c"] samples not None):
        """Add multiple chains stored in a 3D array, assuming all the chains 
        are of the same length.

        Args:
            samples: 3D numpy.ndarray containing the samples with shape 
                (nchains_in, nsamples_in, ndim) and dtype double.
        
        Raises: 
            TypeError: Raised when ndim of new chains does not match previous 
                chains.
        """

        nchains_in = samples.shape[0]
        nsamples_in = samples.shape[1]
        ndim_in = samples.shape[2]

        # Check new chain has correct ndim.
        if ndim_in != self.ndim:            
            raise TypeError("ndim of new chain does not match previous chains")

        cdef int i_chain
        for i_chain in range(nchains_in):
            self.add_chain(samples[i_chain,:,:])

        return
            
    def get_chain_indices(self, int i):
        """Gets the start and end index of samples from a chain.
        
        The end index specifies the index one passed the end of the chain, i.e. 
        the chain samples can be accessed by self.samples[start:end,:].
        
        Args:
            i: Index of chain of which to determine start and end indices.

        Returns:
            A tuple of the start and end index, i.e. (start, end).
            
        Raises:
            ValueError: Raised when chain number invalid.
        """
        
        if i < 0:
            raise ValueError("Chain number must be positive")
        if i >= self.nchains:
            raise ValueError("Chain number is greater than nchains-1")

        return self.start_indices[i], self.start_indices[i+1]
            
    def add(self, other):
        """Add other Chain object to this object.
        
        Args: 
            other: Other Chain object to be added to this object.
        """
                
        if self.ndim != other.ndim:
            raise ValueError("ndim of other Chain object does not match this "
            + "Chain object.")
            
        if other.nsamples == 0:
            return            
        
        self.samples = np.concatenate((self.samples, other.samples))
        self.start_indices = self.start_indices \
             + list(map(lambda x : x + self.nsamples, other.start_indices[1:]))
        self.nchains += other.nchains
        self.nsamples += other.nsamples 
        
        return        
                                                    
    def copy(self):
        """Copy chain.
        """
        
        return copy.copy(self)

    def nsamples_per_chain(self):   
        """Compute list containing number of samples in each chain.
        
        Args:
            None.
        
        Returns:
            nsamples_per_chain: 1D list of length self.nchains containing the number of samples in each chain.
        """
        
        zipped = list(zip(self.start_indices[0:self.nchains],
                          self.start_indices[1:self.nchains+1]))
        
        nsamples_per_chain = list(map(lambda x : x[1] - x[0],  zipped))
        
        return nsamples_per_chain 
        

    def split_into_blocks(self, nblocks=100):
        """TODO
        """
        
        if nblocks <= self.nchains:
            # TODO: display warning
            return
        
        # Compute relative size of chains.
        nsamples_per_chain = np.array(self.nsamples_per_chain())
        
        print("\n")
        print("nsamples_per_chain = {}".format(nsamples_per_chain))
        
        rel_size_chain = nsamples_per_chain / self.nsamples
        
        print("rel_size_chain = {}".format(rel_size_chain))
        #blocking_factor = nblocks / self.nchains
        
        nblocks_per_chain = np.round(nblocks * rel_size_chain).astype(int)
        
        nblocks_per_chain[nblocks_per_chain == 0] = 1
        print("nblocks_per_chain = {}".format(nblocks_per_chain))

        # Ensure no chains have zero blocks due to rounding.
        target_offset = int(nblocks - np.ndarray.sum(nblocks_per_chain))
        print("target_offset = {}".format(target_offset))

        # Potentially adjust blocks per chain due to rounding errors.
        if target_offset != 0:            
            chain_to_adjust = np.argmax(nblocks_per_chain)
            nblocks_per_chain[chain_to_adjust] += target_offset
            if nblocks_per_chain[chain_to_adjust] < 1:
                raise ValueError("Adjusted block number for chain less than 1.")
        print("nblocks_per_chain = {}".format(nblocks_per_chain))
        
        start_indices_new = np.array([0])
        for i_chain in range(self.nchains):
            start = self.start_indices[i_chain]
            end = self.start_indices[i_chain+1]
            
            step = int((end - start) // nblocks_per_chain[i_chain])
            print("chain = {}, start = {}".format(i_chain, start))
            print("chain = {}, end = {}".format(i_chain, end))
            print("chain = {}, step = {}".format(i_chain, step))

            block_start_indices = start + np.array(range(nblocks_per_chain[i_chain]+1), dtype=int) * step
            # block_start_indices = nblocks_per_chain[i_chain]
            
            # block_start_indices = np.arange(start, end, step)
            # step is number of elements in each block so increment all indices except the first by 1
            # block_start_indices[1:] += 1
            block_start_indices[-1] = end
            print("chain = {}, block_start_indices = {}".format(i_chain, block_start_indices))

            start_indices_new = np.concatenate((start_indices_new, block_start_indices[1:]))

            print("chain = {}, start_indices_new = {}".format(i_chain, start_indices_new))
        
        self.start_indices = start_indices_new
        self.nchains = nblocks
        print("nsamples_per_chain = {}".format(self.nsamples_per_chain()))

        
        mean_samples_per_chain = np.mean(self.nsamples_per_chain()) 
        print("mean_samples_per_chain = {}".format(mean_samples_per_chain))
        
        err = np.absolute(mean_samples_per_chain - self.nsamples / nblocks)
        print("err = {}".format(err))
        
        



        return

