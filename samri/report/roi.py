import nibabel as nib
import numpy as np
from os import path

from nilearn.input_data import NiftiMasker
from scipy.io import loadmat
from samri.report.utilities import add_roi_data
from joblib import Parallel, delayed

import statsmodels.formula.api as smf
import multiprocessing as mp
import pandas as pd

def from_threshold(image, threshold,
	save_as=False,
	):

	if isinstance(image,str):
		image = path.abspath(path.expanduser(image))
		image = nib.load(image)
	data = image.get_data()
	header = image.header
	affine = image.affine
	shape = image.shape
	roi_pos = np.where(data>threshold,[True],[False])
	roi_neg = np.where(data<-threshold,[True],[False])
	roi = np.logical_or(roi_pos, roi_neg)
	roi = 1*roi
	roi = nib.Nifti1Image(roi, affine, header)

	if save_as:
		save_as = path.abspath(path.expanduser(save_as))
		nib.save(roi, save_as)

	return roi

def roi_per_session(substitutions, roi_mask,
	filename_template="~/ni_data/ofM.dr/l1/{l1_dir}/sub-{subject}/ses-{session}/sub-{subject}_ses-{session}_trial-{scan}_tstat.nii.gz",
	roi_mask_normalize="",
	):

	"""
	roi_mask : str
	Path to the ROI mask for which to select the t-values.

	roi_mask_normalize : str
	Path to a ROI mask by the mean of whose t-values to normalite the t-values in roi_mask.
	"""

	if isinstance(roi_mask,str):
		roi_mask = path.abspath(path.expanduser(roi_mask))
		roi_mask = nib.load(roi_mask)


	masker = NiftiMasker(mask_img=roi_mask)

	n_jobs = mp.cpu_count()-2
	roi_data = Parallel(n_jobs=n_jobs, verbose=0, backend="threading")(map(delayed(add_roi_data),
		[filename_template]*len(substitutions),
		[masker]*len(substitutions),
		substitutions,
		))
	subject_dfs, voxel_dfs = zip(*roi_data)
	subjectdf = pd.concat(subject_dfs)
	voxeldf = pd.concat(voxel_dfs)
	if roi_mask_normalize:
		#TODO: how relay this back to plot?
		#figure="per-participant"
		if isinstance(roi_mask_normalize,str):
			mask_normalize = path.abspath(path.expanduser(roi_mask_normalize))
		masker_normalize = NiftiMasker(mask_img=mask_normalize)
		roi_data = Parallel(n_jobs=n_jobs, verbose=0, backend="threading")(map(delayed(add_roi_data),
			[filename_template]*len(substitutions),
			[masker_normalize]*len(substitutions),
			substitutions,
			))
		subject_dfs_normalize, _ = zip(*roi_data)
		subjectdf_normalize = pd.concat(subject_dfs_normalize)

		subjectdf['t'] = subjectdf['t']/subjectdf_normalize['t']
		#this is a nasty hack to mitigate +/-inf values appearing if the normalization ROI mean is close to 0
		subjectdf_ = deepcopy(subjectdf)
		subjectdf_= subjectdf_.replace([np.inf, -np.inf], np.nan).dropna(subset=["t"], how="all")
		subjectdf=subjectdf.replace([-np.inf], subjectdf_[['t']].min(axis=0)[0])
		subjectdf=subjectdf.replace([np.inf], subjectdf_[['t']].max(axis=0)[0])

	#model = smf.mixedlm("t ~ session", subjectdf, groups=subjectdf["subject"])
	#fit = model.fit()
	#report = fit.summary()

	# create a restriction for every regressor - except intercept (first) and random effects (last)
	#omnibus_tests = np.eye(len(fit.params))[1:-1]
	#anova = fit.f_test(omnibus_tests)

	return subjectdf, voxeldf


def roi_mean(img_path, mask_path):
	"""Return the mean of the masked region of an image.
	"""
	mask = path.abspath(path.expanduser(mask_path))
	if mask_path.endswith("roi"):
		mask = loadmat(mask)["ROI"]
		while mask.ndim != 3:
			mask=mask[0]
		img_path = path.abspath(path.expanduser(img_path))
		img = nib.load(img_path)
		print(mask)
		print(np.shape(mask))
		print(np.shape(img))
		print(img[mask])
	else:
		masker = NiftiMasker(mask_img=mask)
		add_roi_data(img_path,masker)
