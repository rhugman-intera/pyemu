import os
import sys
from pathlib import Path
import platform

# sys.path.append(os.path.join("..","pyemu"))
import numpy as np
import pandas as pd
import pyemu
from pyemu import os_utils
from pyemu.utils import PstFrom, pp_file_to_dataframe, write_pp_file
import shutil

ext = ''
local_bins = False  # change if wanting to test with local binary exes
if local_bins:
    bin_path = os.path.join("..", "..", "bin")
    if "linux" in platform.platform().lower():
        pass
        bin_path = os.path.join(bin_path, "linux")
    elif "darwin" in platform.platform().lower() or 'macos' in platform.platform().lower():
        pass
        bin_path = os.path.join(bin_path, "mac")
    else:
        bin_path = os.path.join(bin_path, "win")
        ext = '.exe'
else:
    bin_path = ''
    if "windows" in platform.platform().lower():
        ext = '.exe'

mf_exe_path = os.path.join(bin_path, "mfnwt")
mt_exe_path = os.path.join(bin_path, "mt3dusgs")
usg_exe_path = os.path.join(bin_path, "mfusg")
mf6_exe_path = os.path.join(bin_path, "mf6")
pp_exe_path = os.path.join(bin_path, "pestpp-glm")
ies_exe_path = os.path.join(bin_path, "pestpp-ies")
swp_exe_path = os.path.join(bin_path, "pestpp-swp")

mf_exe_name = os.path.basename(mf_exe_path)
mf6_exe_name = os.path.basename(mf6_exe_path)


def _gen_dummy_obs_file(ws='.', sep=',', ext=None):
    import pandas as pd
    ffn = "somefakeobs"
    if ext is None:
        if sep == ',':
            fnme = f'{ffn}.csv'
        else:
            fnme = f'{ffn}.dat'
    else:
        fnme = f'{ffn}.{ext}'
    text = pyemu.__doc__.split(' ', 100)
    t = []
    c = 15
    for s in text[:15]:
        s = s.strip().replace('\n', '')
        if len(s) > 1 and s not in t:
            t.append(s)
        else:
            t.append(text[c])
            c += 1

    df = pd.DataFrame(
        np.random.rand(15,2)*1000,
        columns=['no', 'yes'],
        index=t
    )
    df.index.name = 'idx'
    df.to_csv(os.path.join(ws, fnme), sep=sep)
    return fnme, df


def freyberg_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join("..", "examples", "freyberg_sfr_update")
    nam_file = "freyberg.nam"
    m = flopy.modflow.Modflow.load(nam_file, model_ws=org_model_ws,
                                   check=False, forgive=False,
                                   exe_name=mf_exe_path)
    flopy.modflow.ModflowRiv(m, stress_period_data={
        0: [[0, 0, 0, m.dis.top.array[0, 0], 1.0, m.dis.botm.array[0, 0, 0]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]]]})

    org_model_ws = "temp_pst_from"
    if os.path.exists(org_model_ws):
        shutil.rmtree(org_model_ws)
    m.external_path = "."
    m.change_model_ws(org_model_ws)
    m.write_input()
    print("{0} {1}".format(mf_exe_path, m.name + ".nam"), org_model_ws)
    os_utils.run("{0} {1}".format(mf_exe_path, m.name + ".nam"),
                 cwd=org_model_ws)
    hds_kperk = []
    for k in range(m.nlay):
        for kper in range(m.nper):
            hds_kperk.append([kper, k])
    hds_runline, df = pyemu.gw_utils.setup_hds_obs(
        os.path.join(m.model_ws, f"{m.name}.hds"), kperk_pairs=None, skip=None,
        prefix="hds", include_path=False)

    sfo = flopy.utils.SfrFile(os.path.join(m.model_ws, 'freyberg.sfr.out'))
    sfodf = sfo.get_dataframe()
    sfodf[['kstp', 'kper']] = pd.DataFrame(sfodf.kstpkper.to_list(),
                                           index=sfodf.index)
    sfodf = sfodf.drop('kstpkper', axis=1)
    # just adding a bit of header in for test purposes
    sfo_pp_file = os.path.join(m.model_ws, 'freyberg.sfo.dat')
    with open(sfo_pp_file, 'w') as fp:
        fp.writelines(["This is a post processed sfr output file\n",
                      "Processed into tabular form using the lines:\n",
                      "sfo = flopy.utils.SfrFile('freyberg.sfr.out')\n",
                      "sfo.get_dataframe().to_csv('freyberg.sfo.dat')\n"])
        sfodf.sort_index(axis=1).to_csv(fp, sep=' ', index_label='idx', line_terminator='\n')
    sfodf.sort_index(axis=1).to_csv(os.path.join(m.model_ws, 'freyberg.sfo.csv'),
                 index_label='idx',line_terminator='\n')
    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)

    # sr0 = m.sr
    sr = pyemu.helpers.SpatialReference.from_namfile(
        os.path.join(m.model_ws, m.namefile),
        delr=m.dis.delr, delc=m.dis.delc)
    # set up PstFrom object
    pf = PstFrom(original_d=org_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False)
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    f, fdf = _gen_dummy_obs_file(pf.new_d)
    pf.add_observations(f, index_cols='idx', use_cols='yes')
    pf.add_py_function('pst_from_tests.py', '_gen_dummy_obs_file()',
                       is_pre_cmd=False)
    pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
                        index_cols='obsnme', use_cols='obsval', prefix='hds')
    #   using the ins file generated by pyemu.gw_utils.setup_hds_obs()
    pf.add_observations_from_ins(ins_file='freyberg.hds.dat.ins')
    pf.post_py_cmds.append(hds_runline)
    pf.tmp_files.append(f"{m.name}.hds")
    # sfr outputs to obs
    sfr_idx = ['segment', 'reach', 'kstp', 'kper']
    sfr_use = ["Qaquifer", "Qout", 'width']
    pf.add_observations('freyberg.sfo.dat', insfile=None,
                        index_cols=sfr_idx,
                        use_cols=sfr_use, prefix='sfr',
                        ofile_skip=4, ofile_sep=' ', use_rows=np.arange(0, 50))
    # check obs set up
    sfrobs = pf.obs_dfs[-1].copy()
    sfrobs[["oname","otype",'usecol'] + sfr_idx] = sfrobs.obsnme.apply(
        lambda x: pd.Series(
            dict([s.split(':') for s in x.split('_') if ':' in s])))
    sfrobs.pop("oname")
    sfrobs.pop("otype")
    sfrobs.loc[:, sfr_idx] = sfrobs.loc[:, sfr_idx].astype(int)
    sfrobs_p = sfrobs.pivot_table(index=sfr_idx,
                                  columns=['usecol'], values='obsval')
    sfodf_c = sfodf.set_index(sfr_idx).sort_index()
    sfodf_c.columns = sfodf_c.columns.str.lower()
    assert (sfrobs_p == sfodf_c.loc[sfrobs_p.index,
                                    sfrobs_p.columns]).all().all(), (
        "Mis-match between expected and processed obs values\n",
        sfrobs_p.head(),
        sfodf_c.loc[sfrobs_p.index, sfrobs_p.columns].head())

    pf.tmp_files.append(f"{m.name}.sfr.out")
    pf.extra_py_imports.append('flopy')
    pf.post_py_cmds.extend(
        ["sfo_pp_file = 'freyberg.sfo.dat'",
         "sfo = flopy.utils.SfrFile('freyberg.sfr.out')",
         "sfodf = sfo.get_dataframe()",
         "sfodf[['kstp', 'kper']] = pd.DataFrame(sfodf.kstpkper.to_list(), index=sfodf.index)",
         "sfodf = sfodf.drop('kstpkper', axis=1)",
         "with open(sfo_pp_file, 'w') as fp:",
         "    fp.writelines(['This is a post processed sfr output file\\n', "
         "'Processed into tabular form using the lines:\\n', "
         "'sfo = flopy.utils.SfrFile(`freyberg.sfr.out`)\\n', "
         "'sfo.get_dataframe().to_csv(`freyberg.sfo.dat`)\\n'])",
         "    sfodf.sort_index(axis=1).to_csv(fp, sep=' ', index_label='idx',line_terminator='\\n')"])
    # csv version of sfr obs
    # sfr outputs to obs
    pf.add_observations('freyberg.sfo.csv', insfile=None,
                        index_cols=['segment', 'reach', 'kstp', 'kper'],
                        use_cols=["Qaquifer", "Qout", "width"], prefix='sfr2',
                        ofile_sep=',', obsgp=['qaquifer', 'qout', "width"],
                        use_rows=np.arange(50, 101))
    # check obs set up
    sfrobs = pf.obs_dfs[-1].copy()
    sfrobs[['oname','otype','usecol'] + sfr_idx] = sfrobs.obsnme.apply(
        lambda x: pd.Series(
            dict([s.split(':') for s in x.split('_') if ':' in s])))
    sfrobs.pop("oname")
    sfrobs.pop("otype")
    sfrobs.loc[:, sfr_idx] = sfrobs.loc[:, sfr_idx].astype(int)
    sfrobs_p = sfrobs.pivot_table(index=sfr_idx,
                                  columns=['usecol'], values='obsval')
    sfodf_c = sfodf.set_index(sfr_idx).sort_index()
    sfodf_c.columns = sfodf_c.columns.str.lower()
    assert (sfrobs_p == sfodf_c.loc[sfrobs_p.index,
                                    sfrobs_p.columns]).all().all(), (
        "Mis-match between expected and processed obs values")
    obsnmes = pd.concat([df.obgnme for df in pf.obs_dfs]).unique()
    assert all([gp in obsnmes for gp in ['qaquifer', 'qout']])
    pf.post_py_cmds.append(
        "sfodf.sort_index(axis=1).to_csv('freyberg.sfo.csv', sep=',', index_label='idx')")
    zone_array = np.arange(m.nlay*m.nrow*m.ncol)
    s = lambda x: "zval_"+str(x)
    zone_array = np.array([s(x) for x in zone_array]).reshape(m.nlay,m.nrow,m.ncol)
    # pars
    pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
                      index_cols=[0, 1, 2], use_cols=[3, 5],
                      par_name_base=["rivstage_grid", "rivbot_grid"],
                      mfile_fmt='%10d%10d%10d %15.8F %15.8F %15.8F',
                      pargp='rivbot')
    pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
                      index_cols=[0, 1, 2], use_cols=4)
    pf.add_parameters(filenames=["WEL_0000.dat", "WEL_0001.dat"],
                      par_type="grid", index_cols=[0, 1, 2], use_cols=3,
                      par_name_base="welflux_grid",
                      zone_array=zone_array)
    pf.add_parameters(filenames="WEL_0000.dat",
                      par_type="grid", index_cols=[0, 1, 2], use_cols=3,
                      par_name_base="welflux_grid_direct",
                      zone_array=zone_array,par_style="direct",transform="none")
    pf.add_parameters(filenames=["WEL_0000.dat"], par_type="constant",
                      index_cols=[0, 1, 2], use_cols=3,
                      par_name_base=["flux_const"])
    pf.add_parameters(filenames="rech_1.ref", par_type="grid",
                      zone_array=m.bas6.ibound[0].array,
                      par_name_base="rch_datetime:1-1-1970")
    pf.add_parameters(filenames=["rech_1.ref", "rech_2.ref"],
                      par_type="zone", zone_array=m.bas6.ibound[0].array)
    pf.add_parameters(filenames="rech_1.ref", par_type="pilot_point",
                      zone_array=m.bas6.ibound[0].array,
                      par_name_base="rch_datetime:1-1-1970", pp_space=4)
    pf.add_parameters(filenames="rech_1.ref", par_type="pilot_point",
                      zone_array=m.bas6.ibound[0].array,
                      par_name_base="rch_datetime:1-1-1970", pp_space=1,
                      ult_ubound=100, ult_lbound=0.0)
    pf.add_parameters(filenames="rech_1.ref", par_type="pilot_point",
                      par_name_base="rch_datetime:1-1-1970", pp_space=1,
                      ult_ubound=100, ult_lbound=0.0)
                      

    # add model run command
    pf.mod_sys_cmds.append("{0} {1}".format(mf_exe_name, m.name + ".nam"))
    print(pf.mult_files)
    print(pf.org_files)


    # build pest
    pst = pf.build_pst('freyberg.pst')

    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    df = df.loc[pd.notna(df.mlt_file),:]
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)

    pst.write_input_files(pst_path=pf.new_d)
    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv")
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)

    pst.control_data.noptmax = 0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    assert pst.phi < 1.0e-5, pst.phi


def freyberg_prior_build_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join("..", "examples", "freyberg_sfr_update")
    nam_file = "freyberg.nam"
    m = flopy.modflow.Modflow.load(nam_file, model_ws=org_model_ws,
                                   check=False, forgive=False,
                                   exe_name=mf_exe_path)
    flopy.modflow.ModflowRiv(m, stress_period_data={
        0: [[0, 0, 0, m.dis.top.array[0, 0], 1.0, m.dis.botm.array[0, 0, 0]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]]]})

    welsp = m.wel.stress_period_data.data.copy()
    addwell = welsp[0].copy()
    addwell['k'] = 1
    welsp[0] = np.rec.array(np.concatenate([welsp[0], addwell]))
    samewell = welsp[1].copy()
    samewell['flux'] *= 10
    welsp[1] = np.rec.array(np.concatenate([welsp[1], samewell]))
    m.wel.stress_period_data = welsp

    org_model_ws = "temp_pst_from"
    if os.path.exists(org_model_ws):
        shutil.rmtree(org_model_ws)
    m.external_path = "."
    m.change_model_ws(org_model_ws)
    m.write_input()

    # for exe in [mf_exe_path, mt_exe_path, ies_exe_path]:
    #     shutil.copy(os.path.relpath(exe, '..'), org_model_ws)

    print("{0} {1}".format(mf_exe_path, m.name + ".nam"), org_model_ws)
    os_utils.run("{0} {1}".format(mf_exe_path, m.name + ".nam"),
                 cwd=org_model_ws)
    hds_kperk = []
    for k in range(m.nlay):
        for kper in range(m.nper):
            hds_kperk.append([kper, k])
    hds_runline, df = pyemu.gw_utils.setup_hds_obs(
        os.path.join(m.model_ws, f"{m.name}.hds"), kperk_pairs=None, skip=None,
        prefix="hds", include_path=False)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    sr = pyemu.helpers.SpatialReference.from_namfile(
        os.path.join(m.model_ws, m.namefile),
        delr=m.dis.delr, delc=m.dis.delc)
    # set up PstFrom object
    pf = PstFrom(original_d=org_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False)
    pf.extra_py_imports.append('flopy')
    if "linux" in platform.platform().lower():
        pf.mod_sys_cmds.append("which python")
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
                        index_cols='obsnme', use_cols='obsval', prefix='hds')
    pf.post_py_cmds.append(hds_runline)
    pf.tmp_files.append(f"{m.name}.hds")

    # pars
    v = pyemu.geostats.ExpVario(contribution=1.0, a=2500)
    geostruct = pyemu.geostats.GeoStruct(variograms=v, transform='log')
    # Pars for river list style model file, every entry in columns 3 and 4
    # specifying formatted model file and passing a geostruct  # TODO method for appending specific ult bounds
    # pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
    #                   index_cols=[0, 1, 2], use_cols=[3, 4],
    #                   par_name_base=["rivstage_grid", "rivcond_grid"],
    #                   mfile_fmt='%10d%10d%10d %15.8F %15.8F %15.8F',
    #                   geostruct=geostruct, lower_bound=[0.9, 0.01],
    #                   upper_bound=[1.1, 100.], ult_lbound=[0.3, None])
    # # 2 constant pars applied to columns 3 and 4
    # # this time specifying free formatted model file
    # pf.add_parameters(filenames="RIV_0000.dat", par_type="constant",
    #                   index_cols=[0, 1, 2], use_cols=[3, 4],
    #                   par_name_base=["rivstage", "rivcond"],
    #                   mfile_fmt='free', lower_bound=[0.9, 0.01],
    #                   upper_bound=[1.1, 100.], ult_lbound=[None, 0.01])
    # Pars for river list style model file, every entry in column 4
    pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
                      index_cols=[0, 1, 2], use_cols=[4],
                      par_name_base=["rivcond_grid"],
                      mfile_fmt='%10d%10d%10d %15.8F %15.8F %15.8F',
                      geostruct=geostruct, lower_bound=[0.01],
                      upper_bound=[100.], ult_lbound=[None])
    # constant par applied to column 4
    # this time specifying free formatted model file
    pf.add_parameters(filenames="RIV_0000.dat", par_type="constant",
                      index_cols=[0, 1, 2], use_cols=[4],
                      par_name_base=["rivcond"],
                      mfile_fmt='free', lower_bound=[0.01],
                      upper_bound=[100.], ult_lbound=[0.01])
    # pf.add_parameters(filenames="RIV_0000.dat", par_type="constant",
    #                   index_cols=[0, 1, 2], use_cols=5,
    #                   par_name_base="rivbot",
    #                   mfile_fmt='free', lower_bound=0.9,
    #                   upper_bound=1.1, ult_ubound=100.,
    #                   ult_lbound=0.001)
    # setting up temporal variogram for correlating temporal pars
    date = m.dis.start_datetime
    v = pyemu.geostats.ExpVario(contribution=1.0, a=180.0)  # 180 correlation length
    t_geostruct = pyemu.geostats.GeoStruct(variograms=v, transform='log')
    # looping over temporal list style input files
    # setting up constant parameters for col 3 for each temporal file
    # making sure all are set up with same pargp and geostruct (to ensure correlation)
    # Parameters for wel list style
    well_mfiles = ["WEL_0000.dat", "WEL_0001.dat", "WEL_0002.dat"]
    for t, well_file in enumerate(well_mfiles):
        # passing same temporal geostruct and pargp,
        # date is incremented and will be used for correlation with
        pf.add_parameters(filenames=well_file, par_type="constant",
                          index_cols=[0, 1, 2], use_cols=3,
                          par_name_base="flux", alt_inst_str='kper',
                          datetime=date, geostruct=t_geostruct,
                          pargp='wellflux_t', lower_bound=0.25,
                          upper_bound=1.75)
        date = (pd.to_datetime(date) +
                pd.DateOffset(m.dis.perlen.array[t], 'day'))
    # par for each well (same par through time)
    pf.add_parameters(filenames=well_mfiles,
                      par_type="grid", index_cols=[0, 1, 2], use_cols=3,
                      par_name_base="welflux_grid",
                      zone_array=m.bas6.ibound.array,
                      geostruct=geostruct, lower_bound=0.25, upper_bound=1.75)
    # global constant across all files
    pf.add_parameters(filenames=well_mfiles,
                      par_type="constant",
                      index_cols=[0, 1, 2], use_cols=3,
                      par_name_base=["flux_global"],
                      lower_bound=0.25, upper_bound=1.75)

    # Spatial array style pars - cell-by-cell
    hk_files = ["hk_Layer_{0:d}.ref".format(i) for i in range(1, 4)]
    for hk in hk_files:
        pf.add_parameters(filenames=hk, par_type="grid",
                          zone_array=m.bas6.ibound[0].array,
                          par_name_base="hk", alt_inst_str='lay',
                          geostruct=geostruct,
                          lower_bound=0.01, upper_bound=100.)

    # Pars for temporal array style model files
    date = m.dis.start_datetime  # reset date
    rch_mfiles = ["rech_0.ref", "rech_1.ref", "rech_2.ref"]
    for t, rch_file in enumerate(rch_mfiles):
        # constant par for each file but linked by geostruct and pargp
        pf.add_parameters(filenames=rch_file, par_type="constant",
                          zone_array=m.bas6.ibound[0].array,
                          par_name_base="rch", alt_inst_str='kper',
                          datetime=date, geostruct=t_geostruct,
                          pargp='rch_t', lower_bound=0.9, upper_bound=1.1)
        date = (pd.to_datetime(date) +
                pd.DateOffset(m.dis.perlen.array[t], 'day'))
    # spatially distributed array style pars - cell-by-cell
    # pf.add_parameters(filenames=rch_mfiles, par_type="grid",
    #                   zone_array=m.bas6.ibound[0].array,
    #                   par_name_base="rch",
    #                   geostruct=geostruct)
    pf.add_parameters(filenames=rch_mfiles, par_type="pilot_point",
                      zone_array=m.bas6.ibound[0].array,
                      par_name_base="rch", pp_space=1,
                      ult_ubound=None, ult_lbound=None,
                      geostruct=geostruct, lower_bound=0.9, upper_bound=1.1)
    # global constant recharge par
    pf.add_parameters(filenames=rch_mfiles, par_type="constant",
                      zone_array=m.bas6.ibound[0].array,
                      par_name_base="rch_global", lower_bound=0.9,
                      upper_bound=1.1)
    # zonal recharge pars
    pf.add_parameters(filenames=rch_mfiles,
                      par_type="zone", par_name_base='rch_zone',
                      lower_bound=0.9, upper_bound=1.1, ult_lbound=1.e-6,
                      ult_ubound=100.)


    # add model run command
    pf.mod_sys_cmds.append("{0} {1}".format(mf_exe_name, m.name + ".nam"))
    print(pf.mult_files)
    print(pf.org_files)


    # build pest
    pst = pf.build_pst('freyberg.pst')
    cov = pf.build_prior(fmt="ascii")
    pe = pf.draw(100, use_specsim=True)
    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)

    pst.write_input_files(pst_path=pf.new_d)
    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv")
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)

    pst.control_data.noptmax = 0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    assert pst.phi < 1.0e-5, pst.phi

    pe.to_binary(os.path.join(pf.new_d, 'par.jcb'))

    # quick sweep test?
    pst.pestpp_options["ies_par_en"] = 'par.jcb'
    pst.pestpp_options["ies_num_reals"] = 10
    pst.control_data.noptmax = -1
    # par = pst.parameter_data
    # par.loc[:, 'parval1'] = pe.iloc[0].T
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    # pyemu.os_utils.start_workers(pf.new_d,
    #                              exe_rel_path="pestpp-ies",
    #                              pst_rel_path="freyberg.pst",
    #                              num_workers=20, master_dir="master",
    #                              cleanup=False, port=4005)


def generic_function(wd='.'):
    import pandas as pd
    import numpy as np
    #onames = ["generic_obs_{0}".format(i) for i in range(100)]
    onames = pd.date_range("1-1-2020",periods=100,freq='d')
    df = pd.DataFrame({"index_2":np.arange(100),"simval1":1,"simval2":2,"datetime":onames})
    df.index = df.pop("datetime")
    df.to_csv(os.path.join(wd, "generic.csv"), date_format="%d-%m-%Y %H:%M:%S")
    return df


def another_generic_function(some_arg):
    import pandas as pd
    import numpy as np
    print(some_arg)


def mf6_freyberg_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    # to by pass the issues with flopy
    # shutil.copytree(org_model_ws,tmp_model_ws)
    # sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format(mf6_exe_path), cwd=tmp_model_ws)
    # doctor some of the list par files to add a comment string
    with open(
            os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_1.txt"), 'r') as fr:
        lines = [line for line in fr]
    with open(os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_1.txt"), 'w') as fw:
        fw.write("# comment line explaining this external file\n")
        for line in lines:
            fw.write(line)

    with open(
            os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_2.txt"), 'r') as fr:
        lines = [line for line in fr]
    with open(os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_2.txt"), 'w') as fw:
        fw.write("# comment line explaining this external file\n")
        for line in lines[0:3] + ["# comment mid table \n"] + lines[3:]:
            fw.write(line)

    with open(
            os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_3.txt"), 'r') as fr:
        lines = [line for line in fr]
    with open(os.path.join('temp_pst_from',
                           "freyberg6.wel_stress_period_data_3.txt"), 'w') as fw:
        fw.write("#k i j flux \n")
        for line in lines:
            fw.write(line)

    with open(
            os.path.join('temp_pst_from',
                         "freyberg6.wel_stress_period_data_4.txt"), 'r') as fr:
        lines = [line for line in fr]
    with open(os.path.join('temp_pst_from',
                           "freyberg6.wel_stress_period_data_4.txt"), 'w') as fw:
        fw.write("# comment line explaining this external file\n"
                 "#k i j flux\n")
        for line in lines:
            fw.write(line)

    # generate a test with headers and non spatial idex
    sfr_pkgdf = pd.DataFrame.from_records(m.sfr.packagedata.array)
    l = sfr_pkgdf.columns.to_list()
    l = ['#rno', 'k', 'i', 'j'] + l[2:]
    with open(
            os.path.join('temp_pst_from',
                         "freyberg6.sfr_packagedata.txt"), 'r') as fr:
        lines = [line for line in fr]
    with open(os.path.join('temp_pst_from',
                           "freyberg6.sfr_packagedata_test.txt"), 'w') as fw:
        fw.write(' '.join(l))
        fw.write('\n')
        for line in lines:
            fw.write(line)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    # sr = pyemu.helpers.SpatialReference.from_namfile(
    #     os.path.join(tmp_model_ws, "freyberg6.nam"),
    #     delr=m.dis.delr.array, delc=m.dis.delc.array)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018",
                 chunk_len=1)
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')

    # call generic once so that the output file exists
    os.chdir(template_ws)
    df = generic_function()
    os.chdir("..")
    # add the values in generic to the ctl file
    f, fdf = _gen_dummy_obs_file(pf.new_d, sep=' ')
    pf.add_observations(f, index_cols='idx', use_cols='yes')
    pf.add_py_function('pst_from_tests.py', "_gen_dummy_obs_file(sep=' ')",
                       is_pre_cmd=False)
    pf.add_observations("generic.csv",insfile="generic.csv.ins",index_cols=["datetime","index_2"],use_cols=["simval1","simval2"])
    # add the function call to make generic to the forward run script
    pf.add_py_function("pst_from_tests.py","generic_function()",is_pre_cmd=False)

    # add a function that isnt going to be called directly
    pf.add_py_function("pst_from_tests.py","another_generic_function(some_arg)",is_pre_cmd=None)

    #pf.post_py_cmds.append("generic_function()")
    df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time", use_cols=list(df.columns.values))
    v = pyemu.geostats.ExpVario(contribution=1.0,a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0,a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    with open(os.path.join(template_ws, "inflow1.txt"), 'w') as fp:
        fp.write("# rid type rate idx0 idx1\n")
        fp.write("205 666 500000.0 1 1")
    pf.add_parameters(filenames='inflow1.txt',
                      pargp='inflow1',
                      comment_char='#',
                      use_cols=2,
                      index_cols=0,
                      upper_bound=10,
                      lower_bound=0.1,
                      par_type="grid",
                      )

    with open(os.path.join(template_ws, "inflow2.txt"), 'w') as fp:
        fp.write("# rid type rate idx0 idx1\n")
        fp.write("205 infl 500000.3 1 1\n")
        fp.write("205 div 1 500000.7 1\n")
        fp.write("206 infl 600000.7 1 1\n")
        fp.write("206 div 1 500000.7 1")
    inflow2_pre = pd.read_csv(os.path.join(pf.new_d, "inflow2.txt"),
                              header=None, sep=' ', skiprows=1)
    with open(os.path.join(template_ws, "inflow3.txt"), 'w') as fp:
        fp.write("# rid type rate idx0 idx1\n")
        fp.write("205 infl 700000.3 1 1\n")
        fp.write("205 div 1 500000.7 1\n")
        fp.write("206 infl 800000.7 1 1\n")
        fp.write("206 div 1 500000.7 1")
    inflow3_pre = pd.read_csv(os.path.join(pf.new_d, "inflow3.txt"),
                              header=None, sep=' ', skiprows=1)
    pf.add_parameters(filenames=['inflow2.txt', "inflow3.txt"],
                      pargp='inflow',
                      comment_char='#',
                      use_cols=2,
                      index_cols=[0, 1],
                      upper_bound=10,
                      lower_bound=0.1,
                      par_type="grid",
                      use_rows=[[205, 'infl'], [206, 'infl']],
                      )
    pf.add_parameters(filenames=['inflow2.txt', "inflow3.txt"],
                      pargp='inflow2',
                      comment_char='#',
                      use_cols=3,
                      index_cols=[0, 1],
                      upper_bound=5,
                      lower_bound=-5,
                      par_type="grid",
                      use_rows=[[205, 'div'], [206, 'div']],
                      par_style='a',
                      transform='none'
                      )
    with open(os.path.join(template_ws, "inflow4.txt"), 'w') as fp:
        fp.write("# rid type rate idx0 idx1\n")
        fp.write("204 infl 700000.3 1 1\n")
        fp.write("205 div 1 500000.7 1\n")
        fp.write("206 infl 800000.7 1 1\n")
        fp.write("207 div 1 500000.7 1")

    inflow4_pre = pd.read_csv(os.path.join(pf.new_d, "inflow4.txt"),
                              header=None, sep=' ', skiprows=1)
    pf.add_parameters(filenames="inflow4.txt",
                      pargp='inflow4',
                      comment_char='#',
                      use_cols=2,
                      index_cols=[0, 1],
                      upper_bound=10,
                      lower_bound=0.1,
                      par_type="grid",
                      use_rows=[(204, "infl")],
                      )
    pf.add_parameters(filenames="inflow4.txt",
                      pargp='inflow5',
                      comment_char='#',
                      use_cols=3,
                      index_cols=[0],
                      upper_bound=10,
                      lower_bound=0.1,
                      par_type="grid",
                      use_rows=(1, 3),
                      )
    # pf.add_parameters(filenames=['inflow2.txt'],
    #                   pargp='inflow3',
    #                   comment_char='#',
    #                   use_cols=2,
    #                   index_cols=[0, 1],
    #                   upper_bound=10,
    #                   lower_bound=0.1,
    #                   par_type="grid",
    #                   use_rows=[0, 2],
    #                   )
    ft, ftd = _gen_dummy_obs_file(pf.new_d, sep=',', ext='txt')
    pf.add_parameters(filenames=f, par_type="grid", mfile_skip=1, index_cols=0,
                      use_cols=[2], par_name_base="tmp",
                      pargp="tmp")
    pf.add_parameters(filenames=ft, par_type="grid", mfile_skip=1, index_cols=0,
                      use_cols=[1, 2], par_name_base=["tmp2_1", "tmp2_2"],
                      pargp="tmp2", mfile_sep=',', par_style='direct')
    tags = {"npf_k_":[0.1,10.],"npf_k33_":[.1,10],"sto_ss":[.1,10],"sto_sy":[.9,1.1],"rch_recharge":[.5,1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]),unit="d")
    print(dts)
    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            pf.add_parameters(filenames=arr_files, par_type="grid", par_name_base="rch_gr",
                              pargp="rch_gr", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              geostruct=gr_gs)
            for arr_file in arr_files:
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file,par_type="constant",par_name_base=arr_file.split('.')[1]+"_cn",
                                  pargp="rch_const",zone_array=ib,upper_bound=ub,lower_bound=lb,geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:
            for arr_file in arr_files:
                # these ult bounds are used later in an assert
                # and also are used so that the initial input array files
                # are preserved
                ult_lb = None
                ult_ub = None
                if "npf_k_" in arr_file:
                   ult_ub = 31.0
                   ult_lb = -1.3
                pf.add_parameters(filenames=arr_file,par_type="grid",par_name_base=arr_file.split('.')[1]+"_gr",
                                  pargp=arr_file.split('.')[1]+"_gr",zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  geostruct=gr_gs,ult_ubound=None if ult_ub is None else ult_ub + 1,
                                  ult_lbound=None if ult_lb is None else ult_lb + 1)
                # use a slightly lower ult bound here
                pf.add_parameters(filenames=arr_file, par_type="pilotpoints", par_name_base=arr_file.split('.')[1]+"_pp",
                                  pargp=arr_file.split('.')[1]+"_pp", zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  ult_ubound=None if ult_ub is None else ult_ub - 1,
                                  ult_lbound=None if ult_lb is None else ult_lb - 1,geostruct=gr_gs)

                # use a slightly lower ult bound here
                pf.add_parameters(filenames=arr_file, par_type="constant",
                                  par_name_base=arr_file.split('.')[1] + "_cn",
                                  pargp=arr_file.split('.')[1] + "_cn", zone_array=ib,
                                  upper_bound=ub, lower_bound=lb,geostruct=gr_gs)

    # add SP1 spatially constant, but temporally correlated wel flux pars
    kper = 0
    list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    pf.add_parameters(filenames=list_file, par_type="constant",
                      par_name_base="twel_mlt_{0}".format(kper),
                      pargp="twel_mlt".format(kper), index_cols=[0, 1, 2],
                      use_cols=[3], upper_bound=1.5, lower_bound=0.5,
                      datetime=dts[kper], geostruct=rch_temporal_gs,
                      mfile_skip=1)

    # add temporally indep, but spatially correlated wel flux pars
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base="wel_grid_{0}".format(kper),
                      pargp="wel_{0}".format(kper), index_cols=[0, 1, 2],
                      use_cols=[3], upper_bound=1.5, lower_bound=0.5,
                      geostruct=gr_gs, mfile_skip=1)
    kper = 1
    list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    pf.add_parameters(filenames=list_file, par_type="constant",
                      par_name_base="twel_mlt_{0}".format(kper),
                      pargp="twel_mlt".format(kper), index_cols=[0, 1, 2],
                      use_cols=[3], upper_bound=1.5, lower_bound=0.5,
                      datetime=dts[kper], geostruct=rch_temporal_gs,
                      mfile_skip='#')
    # add temporally indep, but spatially correlated wel flux pars
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base="wel_grid_{0}".format(kper),
                      pargp="wel_{0}".format(kper), index_cols=[0, 1, 2],
                      use_cols=[3], upper_bound=1.5, lower_bound=0.5,
                      geostruct=gr_gs, mfile_skip='#')
    kper = 2
    list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    pf.add_parameters(filenames=list_file, par_type="constant",
                      par_name_base="twel_mlt_{0}".format(kper),
                      pargp="twel_mlt".format(kper), index_cols=['#k', 'i', 'j'],
                      use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
                      datetime=dts[kper], geostruct=rch_temporal_gs)
    # add temporally indep, but spatially correlated wel flux pars
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base="wel_grid_{0}".format(kper),
                      pargp="wel_{0}".format(kper), index_cols=['#k', 'i', 'j'],
                      use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
                      geostruct=gr_gs)
    kper = 3
    list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    pf.add_parameters(filenames=list_file, par_type="constant",
                      par_name_base="twel_mlt_{0}".format(kper),
                      pargp="twel_mlt".format(kper), index_cols=['#k', 'i', 'j'],
                      use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
                      datetime=dts[kper], geostruct=rch_temporal_gs,
                      mfile_skip=1)
    # add temporally indep, but spatially correlated wel flux pars
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base="wel_grid_{0}".format(kper),
                      pargp="wel_{0}".format(kper), index_cols=['#k', 'i', 'j'],
                      use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
                      geostruct=gr_gs, mfile_skip=1)
    list_files = ["freyberg6.wel_stress_period_data_{0}.txt".format(t)
                  for t in range(5, m.nper+1)]
    for list_file in list_files:
        kper = int(list_file.split(".")[1].split('_')[-1]) - 1
        # add spatially constant, but temporally correlated wel flux pars
        pf.add_parameters(filenames=list_file,par_type="constant",par_name_base="twel_mlt_{0}".format(kper),
                          pargp="twel_mlt".format(kper),index_cols=[0,1,2],use_cols=[3],
                          upper_bound=1.5,lower_bound=0.5, datetime=dts[kper], geostruct=rch_temporal_gs)

        # add temporally indep, but spatially correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="grid", par_name_base="wel_grid_{0}".format(kper),
                          pargp="wel_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=1.5, lower_bound=0.5, geostruct=gr_gs)
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base=f"wel_grid_{kper}",
                      pargp=f"wel_{kper}_v2", index_cols=[0, 1, 2], use_cols=[3], use_rows=[1],
                      upper_bound=1.5, lower_bound=0.5, geostruct=gr_gs)
    # test non spatial idx in list like
    pf.add_parameters(filenames="freyberg6.sfr_packagedata_test.txt", par_name_base="sfr_rhk",
                      pargp="sfr_rhk", index_cols=['#rno'], use_cols=['rhk'], upper_bound=10.,
                      lower_bound=0.1,
                      par_type="grid")

    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')

    # # quick check of write and apply method
    pars = pst.parameter_data
    # set reach 1 hk to 100
    sfr_pars = pars.loc[pars.parnme.str.startswith('pname:sfr')].index
    pars.loc[sfr_pars, 'parval1'] = np.random.random(len(sfr_pars)) * 10

    sfr_pars = pars.loc[sfr_pars].copy()
    print(sfr_pars)
    sfr_pars[["name",'inst',"ptype", 'usecol',"pstyle", '#rno']] = sfr_pars.parnme.apply(
        lambda x: pd.DataFrame([s.split(':') for s in x.split('_')
                                if ':' in s]).set_index(0)[1])

    sfr_pars['#rno'] = sfr_pars['#rno'].astype(int)
    os.chdir(pf.new_d)
    dummymult = 4.
    pars = pst.parameter_data
    pst.parameter_data.loc[pars.index.str.contains('_pp'), 'parval1'] = dummymult
    pst.write_input_files()
    try:
        pyemu.helpers.apply_list_and_array_pars()
    except Exception as e:
        os.chdir('..')
        raise e
    os.chdir('..')
    # verify apply
    inflow2_df = pd.read_csv(os.path.join(pf.new_d, "inflow2.txt"),
                             header=None, sep=' ', skiprows=1)
    inflow3_df = pd.read_csv(os.path.join(pf.new_d, "inflow3.txt"),
                             header=None, sep=' ', skiprows=1)
    inflow4_df = pd.read_csv(os.path.join(pf.new_d, "inflow4.txt"),
                             header=None, sep=' ', skiprows=1)
    assert (inflow2_df == inflow2_pre).all().all()
    assert (inflow3_df == inflow3_pre).all().all()
    assert (inflow4_df == inflow4_pre).all().all()
    multinfo = pd.read_csv(os.path.join(pf.new_d, "mult2model_info.csv"),
                           index_col=0)
    ppmultinfo = multinfo.dropna(subset=['pp_file'])
    for mfile in ppmultinfo.model_file.unique():
        subinfo = ppmultinfo.loc[ppmultinfo.model_file == mfile]
        assert subinfo.org_file.nunique() == 1
        org = np.loadtxt(os.path.join(pf.new_d, subinfo.org_file.values[0]))
        m = dummymult ** len(subinfo)
        check = org * m
        check[ib == 0] = org[ib == 0]
        ult_u = subinfo.upper_bound.astype(float).values[0]
        ult_l = subinfo.lower_bound.astype(float).values[0]
        check[check < ult_l] = ult_l
        check[check > ult_u] = ult_u
        result = np.loadtxt(os.path.join(pf.new_d, mfile))
        assert np.isclose(check, result).all(), (f"Problem with par apply for "
                                                 f"{mfile}")
    df = pd.read_csv(os.path.join(
        pf.new_d, "freyberg6.sfr_packagedata_test.txt"),
        delim_whitespace=True, index_col=0)
    df.index = df.index - 1
    print(df.rhk)
    print((sfr_pkgdf.set_index('rno').loc[df.index, 'rhk'] *
                 sfr_pars.set_index('#rno').loc[df.index, 'parval1']))
    assert np.isclose(
        df.rhk, (sfr_pkgdf.set_index('rno').loc[df.index, 'rhk'] *
                 sfr_pars.set_index('#rno').loc[df.index, 'parval1'])).all()
    pars.loc[sfr_pars.index, 'parval1'] = 1.0

    # add more:
    pf.add_parameters(filenames="freyberg6.sfr_packagedata.txt", par_name_base="sfr_rhk",
                      pargp="sfr_rhk", index_cols={'k': 1, 'i': 2, 'j': 3}, use_cols=[9], upper_bound=10.,
                      lower_bound=0.1,
                      par_type="grid", rebuild_pst=True)

    df = pd.read_csv(os.path.join(tmp_model_ws, "heads.csv"), index_col=0)
    pf.add_observations("heads.csv", insfile="heads.csv.ins", index_cols="time", use_cols=list(df.columns.values),
                        prefix="hds", rebuild_pst=True)

    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv", chunk_len=1)
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)

    cov = pf.build_prior(fmt="none").to_dataframe()
    twel_pars = [p for p in pst.par_names if "twel_mlt" in p]
    twcov = cov.loc[twel_pars,twel_pars]
    dsum = np.diag(twcov.values).sum()
    assert twcov.sum().sum() > dsum

    rch_cn = [p for p in pst.par_names if "_cn" in p]
    print(rch_cn)
    rcov = cov.loc[rch_cn,rch_cn]
    dsum = np.diag(rcov.values).sum()
    assert rcov.sum().sum() > dsum

    num_reals = 100
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[1], pst.npar_adj)
    assert pe.shape[0] == num_reals


    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","

    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    #assert pst.phi < 1.0e-5, pst.phi

    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.dropna().unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)

    # make sure the appropriate ult bounds have made it thru
    df = pd.read_csv(os.path.join(template_ws,"mult2model_info.csv"))
    print(df.columns)
    df = df.loc[df.model_file.apply(lambda x: "npf_k_" in x),:]
    print(df)
    print(df.upper_bound)
    print(df.lower_bound)
    assert np.abs(float(df.upper_bound.min()) - 30.) < 1.0e-6,df.upper_bound.min()
    assert np.abs(float(df.lower_bound.max()) - -0.3) < 1.0e-6,df.lower_bound.max()


def mf6_freyberg_shortnames_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    # os.mkdir(tmp_model_ws)
    # sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # # sim.set_all_data_external()
    # sim.set_sim_path(tmp_model_ws)
    # # sim.set_all_data_external()
    # m = sim.get_model("freyberg6")
    # sim.set_all_data_external()
    # sim.write_simulation()

    # to by pass the issues with flopy
    shutil.copytree(org_model_ws,tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format("mf6"), cwd=tmp_model_ws)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    sr = pyemu.helpers.SpatialReference.from_namfile(
        os.path.join(tmp_model_ws, "freyberg6.nam"),
        delr=m.dis.delr.array, delc=m.dis.delc.array)
    # set up PstFrom object
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')

    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=False, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018")
    df = pd.read_csv(os.path.join(tmp_model_ws,"heads.csv"), index_col=0)
    pf.add_observations("heads.csv",insfile="heads.csv.ins", index_cols="time",
                        use_cols=list(df.columns.values), prefix="hds")
    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0,a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_":[0.1,10.],"npf_k33_":[.1,10],"sto_ss":[.1,10],"sto_sy":[.9,1.1],"rch_recharge":[.5,1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]),unit="d")
    print(dts)
    for tag,bnd in tags.items():
        lb,ub = bnd[0],bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws)
                     if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            pf.add_parameters(filenames=arr_files, par_type="grid", par_name_base="rg",
                              pargp="rg", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              geostruct=gr_gs)
            for arr_file in arr_files:
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file,par_type="constant",par_name_base="rc{0}_".format(kper),
                                  pargp="rc",zone_array=ib,upper_bound=ub,lower_bound=lb,geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:

            for arr_file in arr_files:
                pb = tag.split('_')[1] + arr_file.split('.')[1][-1]
                pf.add_parameters(filenames=arr_file,par_type="grid",par_name_base=pb+"g",
                                  pargp=pb+"g",zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  geostruct=gr_gs)
                pf.add_parameters(filenames=arr_file, par_type="pilotpoints", par_name_base=pb+"p",
                                  pargp=pb+"p", zone_array=ib,upper_bound=ub,lower_bound=lb,)
        for arr_file in arr_files:
            pf.add_observations(arr_file)
    list_files = [f for f in os.listdir(tmp_model_ws) if "wel_stress_period_data" in f]
    for list_file in list_files:
        kper = list_file.split(".")[1].split('_')[-1]
        pf.add_parameters(filenames=list_file,par_type="constant",par_name_base="w{0}".format(kper),
                          pargp="wel_{0}".format(kper),index_cols=[0,1,2],use_cols=[3],
                          upper_bound=1.5,lower_bound=0.5)
    za = np.ones((3, 40, 20))
    df = pd.read_csv(os.path.join(m.model_ws, list_file),
                     delim_whitespace=True, header=None) - 1
    za[tuple(df.loc[0:2, [0, 1, 2]].values.T)] = [2,3,4]
    pdf = pf.add_parameters(filenames=list_file, par_type="zone",
                            par_name_base="w{0}".format(kper),
                            pargp="wz_{0}".format(kper), index_cols=[0, 1, 2],
                            use_cols=[3],
                            upper_bound=1.5, lower_bound=0.5,
                            zone_array=za)
    assert len(pdf) == 4

    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')
    obs = set(pst.observation_data.obsnme)
    obsin = set()
    for ins in pst.instruction_files:
        with open(os.path.join(pf.new_d, ins), "rt") as f:
            text = f.read()
            for ob in obs:
                if f"!{ob}!" in text:
                    obsin.add(ob)
        obs = obs - obsin
    assert len(obs) == 0, f"{len(obs)} obs not found in insfiles: {obs}"

    par = set(pst.parameter_data.parnme)
    parin = set()
    for tpl in pst.template_files:
        with open(os.path.join(pf.new_d, tpl), "rt") as f:
            text = f.read()
            for p in par:
                if f"{p} " in text:
                    parin.add(p)
        par = par - parin
    assert len(par) == 0, f"{len(par)} pars not found in tplfiles: {par}"
    # test update/rebuild
    pf.add_parameters(filenames="freyberg6.sfr_packagedata.txt",
                      par_name_base="rhk",
                      pargp="sfr_rhk", index_cols=[0, 1, 2, 3], use_cols=[9],
                      upper_bound=10., lower_bound=0.1,
                      par_type="grid", rebuild_pst=True)
    pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base=pb + "g2",
                      pargp=pb + "g2", zone_array=ib, upper_bound=ub, lower_bound=lb,
                      geostruct=gr_gs, rebuild_pst=True)
    df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time",
                        use_cols=list(df.columns.values), rebuild_pst=True)
    obs = set(pst.observation_data.obsnme)
    obsin = set()
    for ins in pst.instruction_files:
        with open(os.path.join(pf.new_d, ins), "rt") as f:
            text = f.read()
            for ob in obs:
                if f"!{ob}!" in text:
                    obsin.add(ob)
            obs = obs - obsin
    assert len(obs) == 0, f"{len(obs)} obs not found in insfiles: {obs}"

    par = set(pst.parameter_data.parnme)
    parin = set()
    for tpl in pst.template_files:
        with open(os.path.join(pf.new_d, tpl), "rt") as f:
            text = f.read()
            for p in par:
                if f"{p} " in text:
                    parin.add(p)
        par = par - parin
    assert len(par) == 0, f"{len(par)} pars not found in tplfiles: {par}"

    assert pst.parameter_data.parnme.apply(lambda x: len(x)).max() <= 12
    assert pst.observation_data.obsnme.apply(lambda x: len(x)).max() <= 20

    num_reals = 100
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[0], pst.npar_adj)
    assert pe.shape[0] == num_reals

    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv")
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)
    pst.try_parse_name_metadata()
    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","

    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    pst = pyemu.Pst(os.path.join(pf.new_d, "freyberg.pst"))
    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    #assert pst.phi < 1.0e-5, pst.phi



    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)


def mf6_freyberg_da_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6_da')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    # to by pass the issues with flopy
    shutil.copytree(org_model_ws,tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format("mf6"), cwd=tmp_model_ws)

    template_ws = "new_temp_da"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    sr = pyemu.helpers.SpatialReference.from_namfile(
        os.path.join(tmp_model_ws, "freyberg6.nam"),
        delr=m.dis.delr.array, delc=m.dis.delc.array)
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False,start_datetime="1-1-2018")
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')

    df = pd.read_csv(os.path.join(tmp_model_ws,"heads.csv"),index_col=0)
    pf.add_observations("heads.csv",insfile="heads.csv.ins",index_cols="time",use_cols=list(df.columns.values),prefix="hds")
    df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time", use_cols=list(df.columns.values))
    v = pyemu.geostats.ExpVario(contribution=1.0,a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0,a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_":[0.1,10.],"npf_k33_":[.1,10],"sto_ss":[.1,10],"sto_sy":[.9,1.1],"rch_recharge":[.5,1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]),unit="d")
    print(dts)
    for tag,bnd in tags.items():
        lb,ub = bnd[0],bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            pf.add_parameters(filenames=arr_files, par_type="grid", par_name_base="rch_gr",
                              pargp="rch_gr", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              geostruct=gr_gs)
            for arr_file in arr_files:
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file,par_type="constant",par_name_base=arr_file.split('.')[1]+"_cn",
                                  pargp="rch_const",zone_array=ib,upper_bound=ub,lower_bound=lb,geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:
            for arr_file in arr_files:
                pf.add_parameters(filenames=arr_file,par_type="grid",par_name_base=arr_file.split('.')[1]+"_gr",
                                  pargp=arr_file.split('.')[1]+"_gr",zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  geostruct=gr_gs)
                pf.add_parameters(filenames=arr_file, par_type="pilotpoints", par_name_base=arr_file.split('.')[1]+"_pp",
                                  pargp=arr_file.split('.')[1]+"_pp", zone_array=ib,upper_bound=ub,lower_bound=lb,)


    list_files = [f for f in os.listdir(tmp_model_ws) if "wel_stress_period_data" in f]
    for list_file in list_files:
        kper = int(list_file.split(".")[1].split('_')[-1]) - 1
        # add spatially constant, but temporally correlated wel flux pars
        pf.add_parameters(filenames=list_file,par_type="constant",par_name_base="twel_mlt_{0}".format(kper),
                          pargp="twel_mlt".format(kper),index_cols=[0,1,2],use_cols=[3],
                          upper_bound=1.5,lower_bound=0.5, datetime=dts[kper], geostruct=rch_temporal_gs)

        # add temporally indep, but spatially correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="grid", par_name_base="wel_grid_{0}".format(kper),
                          pargp="wel_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=1.5, lower_bound=0.5, geostruct=gr_gs)

    pf.add_parameters(filenames="freyberg6.sfr_packagedata.txt",par_name_base="sfr_rhk",
                      pargp="sfr_rhk",index_cols={'k':1,'i':2,'j':3},use_cols=[9],upper_bound=10.,lower_bound=0.1,
                      par_type="grid")

    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst', version=2)
    pst.write(os.path.join(template_ws,"freyberg6_da.pst"),version=2)


    # setup direct (non mult) pars on the IC files with par names that match the obs names
    obs = pst.observation_data
    hobs = obs.loc[obs.obsnme.str.startswith("hds"),:].copy()
    hobs.loc[:,"k"] = hobs.obsnme.apply(lambda x: int(x.split(':')[1].split("_")[1]))
    hobs.loc[:, "i"] = hobs.obsnme.apply(lambda x: int(x.split(':')[1].split("_")[2]))
    hobs.loc[:, "j"] = hobs.obsnme.apply(lambda x: int(x.split(':')[1].split("_")[3]))
    hobs_set = set(hobs.obsnme.to_list())
    ic_files = [f for f in os.listdir(template_ws) if "ic_strt" in f and f.endswith(".txt")]
    print(ic_files)
    ib = m.dis.idomain[0].array
    tpl_files = []
    for ic_file in ic_files:
        tpl_file = os.path.join(template_ws,ic_file+".tpl")
        vals,names = [],[]
        with open(tpl_file,'w') as f:
            f.write("ptf ~\n")
            k = int(ic_file.split('.')[1][-1]) - 1
            org_arr = np.loadtxt(os.path.join(template_ws,ic_file))
            for i in range(org_arr.shape[0]):
                for j in range(org_arr.shape[1]):
                    if ib[i,j] < 1:
                        f.write(" -1.0e+30 ")
                    else:
                        pname = "hds_usecol:trgw_{0}_{1}_{2}_time:31.0".format(k,i,j)
                        if pname not in hobs_set and ib[i,j] > 0:
                            print(k,i,j,pname,ib[i,j])
                        f.write(" ~  {0}   ~".format(pname))
                        vals.append(org_arr[i,j])
                        names.append(pname)
                f.write("\n")
        df = pf.pst.add_parameters(tpl_file,pst_path=".")
        pf.pst.parameter_data.loc[df.parnme,"partrans"] = "fixed"
        pf.pst.parameter_data.loc[names,"parval1"] = vals

    pf.pst.write(os.path.join(template_ws,"freyberg6_da.pst"),version=2)

    num_reals = 100
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[0], pst.npar_adj)
    assert pe.shape[0] == num_reals

    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv")
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)

    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","

    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    #assert pst.phi < 1.0e-5, pst.phi



    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)


def mf6_freyberg_direct_test():

    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from_direct"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external()
    sim.write_simulation()

    # to by pass the issues with flopy
    # shutil.copytree(org_model_ws,tmp_model_ws)
    # sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format("mf6"), cwd=tmp_model_ws)

    template_ws = "new_temp_direct"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018")
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')


    ghb_files = [f for f in os.listdir(template_ws) if ".ghb_stress" in f and f.endswith("txt")]
    pf.add_parameters(ghb_files,par_type="grid",par_style="add",use_cols=3,par_name_base="ghbstage",
                      pargp="ghbstage",index_cols=[0,1,2],transform="none",lower_bound=-5,upper_bound=5)

    pf.add_parameters(ghb_files, par_type="grid", par_style="multiplier", use_cols=3, par_name_base="mltstage",
                      pargp="ghbstage", index_cols=[0, 1, 2], transform="log", lower_bound=0.5,
                      upper_bound=1.5)

    # Add stream flow observation
    # df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time",
                        use_cols=["GAGE_1","HEADWATER","TAILWATER"],ofile_sep=",")
    # Setup geostruct for spatial pars
    gr_v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=gr_v, transform="log")
    pp_v = pyemu.geostats.ExpVario(contribution=1.0, a=5000)
    pp_gs = pyemu.geostats.GeoStruct(variograms=pp_v, transform="log")
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0, a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_": [0.1, 10.], "npf_k33_": [.1, 10], "sto_ss": [.1, 10], "sto_sy": [.9, 1.1],
            "rch_recharge": [.5, 1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]), unit="d")
    print(dts)
    #ib = m.dis.idomain.array[0,:,:]
    # setup from array style pars
    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            for arr_file in arr_files:
                # indy direct grid pars for each array type file
                recharge_files = ["recharge_1.txt","recharge_2.txt","recharge_3.txt"]
                pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base="rch_gr",
                                  pargp="rch_gr", zone_array=ib, upper_bound=1.0e-3, lower_bound=1.0e-7,
                                  par_style="direct")
                # additional constant mults
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file, par_type="constant",
                                  par_name_base=arr_file.split('.')[1] + "_cn",
                                  pargp="rch_const", zone_array=ib, upper_bound=ub, lower_bound=lb,
                                  geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:
            for arr_file in arr_files:
                # grid mults pure and simple
                pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base=arr_file.split('.')[1] + "_gr",
                                  pargp=arr_file.split('.')[1] + "_gr", zone_array=ib, upper_bound=ub,
                                  lower_bound=lb,
                                  geostruct=gr_gs)

    # Add a variety of list style pars
    list_files = ["freyberg6.wel_stress_period_data_{0}.txt".format(t)
                  for t in range(1, m.nper + 1)]
    # make dummy versions with headers
    for fl in list_files[0:2]: # this adds a header to well file
        with open(os.path.join(template_ws, fl), 'r') as fr:
            lines = [line for line in fr]
        with open(os.path.join(template_ws, f"new_{fl}"), 'w') as fw:
            fw.write("k i j flux \n")
            for line in lines:
                fw.write(line)

    # fl = "freyberg6.wel_stress_period_data_3.txt" # Add extra string col_id
    for fl in list_files[2:7]:
        with open(os.path.join(template_ws, fl), 'r') as fr:
            lines = [line for line in fr]
        with open(os.path.join(template_ws, f"new_{fl}"), 'w') as fw:
            fw.write("well k i j flux \n")
            for i, line in enumerate(lines):
                fw.write(f"well{i}" + line)


    list_files.sort()
    for list_file in list_files:
        kper = int(list_file.split(".")[1].split('_')[-1]) - 1
        #add spatially constant, but temporally correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="constant", par_name_base="twel_mlt_{0}".format(kper),
                          pargp="twel_mlt_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=1.5, lower_bound=0.5, datetime=dts[kper], geostruct=rch_temporal_gs)

        # add temporally indep, but spatially correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="grid", par_name_base="wel_grid_{0}".format(kper),
                          pargp="wel_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=0.0, lower_bound=-1000, geostruct=gr_gs, par_style="direct",
                          transform="none")
    # Adding dummy list pars with different file structures
    list_file = "new_freyberg6.wel_stress_period_data_1.txt"  # with a header
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nwell_mlt',
                      pargp='nwell_mult', index_cols=['k', 'i', 'j'], use_cols='flux',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs,
                      transform="none")
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nwell_grid',
                      pargp='nwell', index_cols=['k', 'i', 'j'], use_cols='flux',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none")
    # with skip instead
    list_file = "new_freyberg6.wel_stress_period_data_2.txt"
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nwell_grid',
                      pargp='nwell', index_cols=[0, 1, 2], use_cols=3,
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none", mfile_skip=1)

    list_file = "new_freyberg6.wel_stress_period_data_3.txt"
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nwell_mlt',
                      pargp='nwell_mult', index_cols=['well', 'k', 'i', 'j'], use_cols='flux',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs,
                      transform="none")
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nwell_grid',
                      pargp='nwell', index_cols=['well', 'k', 'i', 'j'], use_cols='flux',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none")
    # with skip instead
    list_file = "new_freyberg6.wel_stress_period_data_4.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base='nwell_grid', pargp='nwell',
                      index_cols=[0, 1, 2, 3],  # or... {'well': 0, 'k': 1, 'i': 2, 'j': 3},
                      use_cols=4, upper_bound=10, lower_bound=-10,
                      geostruct=gr_gs, par_style="direct", transform="none",
                      mfile_skip=1)

    list_file = "freyberg6.ghb_stress_period_data_1.txt"
    pf.add_parameters(filenames=list_file, par_type="constant", par_name_base=["ghb_stage","ghb_cond"],
                      pargp=["ghb_stage","ghb_cond"], index_cols=[0, 1, 2], use_cols=[3,4],
                      upper_bound=[35,150], lower_bound=[32,50], par_style="direct",
                      transform="none")

    dup_file = "freyberg6.wel_stress_period_data_with_dups.txt"
    shutil.copy2(os.path.join("utils", dup_file), os.path.join(pf.new_d, dup_file))
    pf.add_parameters(filenames=dup_file, par_type="grid", par_name_base="dups",
                      pargp="dups", index_cols=[0, 1, 2], use_cols=[3],
                      upper_bound=0.0, lower_bound=-500,par_style="direct",
                      transform="none")

    list_file = "new_freyberg6.wel_stress_period_data_5.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base=['nwell5_k', 'nwell5_q'],
                      pargp='nwell5',
                      index_cols=['well', 'i',  'j'],
                      use_cols=['k', 'flux'], upper_bound=10, lower_bound=-10,
                      geostruct=gr_gs, par_style="direct", transform="none",
                      mfile_skip=0, use_rows=[3, 4])

    list_file = "new_freyberg6.wel_stress_period_data_6.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base=['nwell6_k', 'nwell6_q'],
                      pargp='nwell6',
                      index_cols=['well', 'i',  'j'],
                      use_cols=['k', 'flux'], upper_bound=10, lower_bound=-10,
                      geostruct=gr_gs, par_style="direct", transform="none",
                      mfile_skip=0, use_rows=[(3, 21, 15), (3, 30, 7)])
    # use_rows should match so all should be setup 2 cols 6 rows
    assert len(pf.par_dfs[-1]) == 2*6 # should be
    list_file = "new_freyberg6.wel_stress_period_data_7.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base=['nwell6_k', 'nwell6_q'],
                      pargp='nwell6',
                      index_cols=['well', 'i',  'j'],
                      use_cols=['k', 'flux'], upper_bound=10, lower_bound=-10,
                      geostruct=gr_gs, par_style="direct", transform="none",
                      mfile_skip=0,
                      use_rows=[('well2', 21, 15), ('well4', 30, 7)])
    assert len(pf.par_dfs[-1]) == 2 * 2  # should be
    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')
    cov = pf.build_prior(fmt="non")
    cov.to_coo("prior.jcb")
    pst.try_parse_name_metadata()
    df = pd.read_csv(os.path.join(tmp_model_ws, "heads.csv"), index_col=0)
    pf.add_observations("heads.csv", insfile="heads.csv.ins", index_cols="time",
                        use_cols=list(df.columns.values),
                        prefix="hds", rebuild_pst=True)

    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    pst.write_input_files()
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv", chunk_len=1)
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    # TODO Some checks on resultant par files...
    list_files = [f for f in os.listdir('.')
                  if f.startswith('new_') and f.endswith('txt')]
    # check on that those dummy pars compare to the model versions.
    for f in list_files:
        n_df = pd.read_csv(f, sep="\s+")
        o_df = pd.read_csv(f.strip('new_'), sep="\s+", header=None)
        o_df.columns = ['k', 'i', 'j', 'flux']
        assert np.isclose(n_df.loc[:, o_df.columns], o_df).all(), (
            "Something broke with alternative style model files"
        )
    os.chdir(b_d)

    num_reals = 100
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[0], pst.npar_adj)
    assert pe.shape[0] == num_reals

    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","

    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    assert pst.phi < 0.1, pst.phi

    org_ghb = pd.read_csv(os.path.join(pf.new_d,"org","freyberg6.ghb_stress_period_data_1.txt"),
                          header=None,names=["l","r","c","stage","cond"])
    new_ghb = pd.read_csv(os.path.join(pf.new_d, "freyberg6.ghb_stress_period_data_1.txt"),
                          delim_whitespace=True,
                          header=None, names=["l", "r", "c", "stage", "cond"])
    d = org_ghb.stage - new_ghb.stage
    print(d)
    assert d.sum() == 0,d.sum()


    # test the additive ghb stage pars
    par = pst.parameter_data
    par.loc[par.parnme.str.contains("ghbstage_inst:0"),"parval1"] = 3.0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    org_ghb = pd.read_csv(os.path.join(pf.new_d, "org", "freyberg6.ghb_stress_period_data_1.txt"),
                          header=None, names=["l", "r", "c", "stage", "cond"])
    new_ghb = pd.read_csv(os.path.join(pf.new_d, "freyberg6.ghb_stress_period_data_1.txt"),
                          delim_whitespace=True,
                          header=None, names=["l", "r", "c", "stage", "cond"])
    d = (org_ghb.stage - new_ghb.stage).apply(np.abs)
    print(d)
    assert d.mean() == 3.0, d.mean()



    # check that the interaction between the direct ghb stage par and the additive ghb stage pars
    # is working
    par.loc[par.parnme.str.contains("ghb_stage"),"parval1"] -= 3.0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    org_ghb = pd.read_csv(os.path.join(tmp_model_ws,"freyberg6.ghb_stress_period_data_1.txt"),
                          header=None, names=["l", "r", "c", "stage", "cond"],delim_whitespace=True)
    new_ghb = pd.read_csv(os.path.join(pf.new_d, "freyberg6.ghb_stress_period_data_1.txt"),
                          delim_whitespace=True,
                          header=None, names=["l", "r", "c", "stage", "cond"])
    d = org_ghb.stage - new_ghb.stage
    print(new_ghb.stage)
    print(org_ghb.stage)
    print(d)
    assert d.sum() == 0.0, d.sum()


    # check the interaction with multiplicative ghb stage, direct ghb stage and additive ghb stage
    par.loc[par.parnme.str.contains("mltstage"), "parval1"] = 1.1
    #par.loc[par.parnme.str.contains("ghbstage_inst:0"), "parval1"] = 0.0
    #par.loc[par.parnme.str.contains("ghb_stage"), "parval1"] += 3.0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    org_ghb = pd.read_csv(os.path.join(tmp_model_ws, "freyberg6.ghb_stress_period_data_1.txt"),
                          header=None, names=["l", "r", "c", "stage", "cond"], delim_whitespace=True)
    new_ghb = pd.read_csv(os.path.join(pf.new_d, "freyberg6.ghb_stress_period_data_1.txt"),
                          delim_whitespace=True,
                          header=None, names=["l", "r", "c", "stage", "cond"])
    d = (org_ghb.stage * 1.1) - new_ghb.stage
    print(new_ghb.stage)
    print(org_ghb.stage)
    print(d)
    assert d.sum() == 0.0, d.sum()



    # turn direct recharge to min and direct wel to min and
    # check that the model results are consistent
    par = pst.parameter_data
    rch_par = par.loc[par.parnme.apply(
        lambda x: "pname:rch_gr" in x and "ptype:gr_pstyle:d" in x ), "parnme"]
    wel_par = par.loc[par.parnme.apply(
        lambda x: "pname:wel_grid" in x and "ptype:gr_usecol:3_pstyle:d" in x), "parnme"]
    par.loc[rch_par,"parval1"] = par.loc[rch_par, "parlbnd"]
    # this should set wells to zero since they are negative values in the control file
    par.loc[wel_par,"parval1"] = par.loc[wel_par, "parubnd"]
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    lst = flopy.utils.Mf6ListBudget(os.path.join(pf.new_d, "freyberg6.lst"))
    flx, cum = lst.get_dataframes(diff=True)
    wel_tot = flx.wel.apply(np.abs).sum()
    print(flx.wel)
    assert wel_tot < 1.0e-6, wel_tot

    rch_files = [f for f in os.listdir(pf.new_d)
                 if ".rch_recharge" in f and f.endswith(".txt")]
    rch_val = par.loc[rch_par,"parval1"][0]
    i, j = par.loc[rch_par, ["i", 'j']].astype(int).values.T
    for rch_file in rch_files:
        arr = np.loadtxt(os.path.join(pf.new_d, rch_file))[i, j]
        print(rch_file, rch_val, arr.mean(), arr.max(), arr.min())
        if np.abs(arr.max() - rch_val) > 1.0e-6 or np.abs(arr.min() - rch_val) > 1.0e-6:
            raise Exception("recharge too diff")


def mf6_freyberg_varying_idomain():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    #sim = None
    ib_file = os.path.join(tmp_model_ws,"freyberg6.dis_idomain_layer1.txt")
    arr = np.loadtxt(ib_file,dtype=np.int64)

    arr[:2,:14] = 0
    np.savetxt(ib_file,arr,fmt="%2d")
    print(arr)

    sim = flopy.mf6.MFSimulation.load(sim_ws=tmp_model_ws)
    m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format(mf6_exe_path), cwd=tmp_model_ws)



    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)

    # if os.path.exists(template_ws):
    #     shutil.rmtree(template_ws)
    # shutil.copytree(tmp_model_ws,template_ws)
    # hk_file = os.path.join(template_ws, "freyberg6.npf_k_layer1.txt")
    # hk = np.loadtxt(hk_file)
    #
    # hk[arr == 0] = 1.0e+30
    # np.savetxt(hk_file,hk,fmt="%50.45f")
    # os_utils.run("{0} ".format(mf6_exe_path), cwd=template_ws)
    # import matplotlib.pyplot as plt
    # hds1 = flopy.utils.HeadFile(os.path.join(tmp_model_ws, "freyberg6_freyberg.hds"))
    # hds2 = flopy.utils.HeadFile(os.path.join(template_ws, "freyberg6_freyberg.hds"))
    #
    # d = hds1.get_data() - hds2.get_data()
    # for dd in d:
    #     cb = plt.imshow(dd)
    #     plt.colorbar(cb)
    #     plt.show()
    # return

    # sr0 = m.sr
    # sr = pyemu.helpers.SpatialReference.from_namfile(
    #     os.path.join(tmp_model_ws, "freyberg6.nam"),
    #     delr=m.dis.delr.array, delc=m.dis.delc.array)

    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018")


    # pf.post_py_cmds.append("generic_function()")
    df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time", use_cols=list(df.columns.values),
                        ofile_sep=",")
    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0, a=60))
    pf.extra_py_imports.append('flopy')

    ib = {}
    for k in range(m.dis.nlay.data):
        a = m.dis.idomain.array[k,:,:].copy()
        print(a)
        ib[k] = a

    tags = {"npf_k_": [0.1, 10.,0.003,35]}#, "npf_k33_": [.1, 10], "sto_ss": [.1, 10], "sto_sy": [.9, 1.1]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]), unit="d")
    print(dts)
    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        ult_lb = bnd[2]
        ult_ub = bnd[3]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]

        for arr_file in arr_files:

            # these ult bounds are used later in an assert

            k = int(arr_file.split(".")[-2].split("layer")[1].split("_")[0]) - 1
            pf.add_parameters(filenames=arr_file, par_type="pilotpoints", par_name_base=arr_file.split('.')[1] + "_pp",
                              pargp=arr_file.split('.')[1] + "_pp", upper_bound=ub, lower_bound=lb,
                              geostruct=gr_gs, zone_array=ib[k],ult_lbound=ult_lb,ult_ubound=ult_ub)

    # add model run command
    pf.mod_sys_cmds.append("mf6")
    df = pd.read_csv(os.path.join(tmp_model_ws, "heads.csv"), index_col=0)
    df = pf.add_observations("heads.csv", insfile="heads.csv.ins", index_cols="time", use_cols=list(df.columns.values),
                        prefix="hds", ofile_sep=",")


    #pst = pf.build_pst('freyberg.pst')
    pf.parfile_relations.to_csv(os.path.join(pf.new_d, "mult2model_info.csv"))
    os.chdir(pf.new_d)
    df = pyemu.helpers.calc_array_par_summary_stats()
    os.chdir("..")
    pf.post_py_cmds.append("pyemu.helpers.calc_array_par_summary_stats()")
    pf.add_observations("arr_par_summary.csv",index_cols=["model_file"],use_cols=df.columns.tolist(),
                        obsgp=["arr_par_summary" for _ in df.columns],prefix=["arr_par_summary" for _ in df.columns])
    pst = pf.build_pst('freyberg.pst')
    pst.control_data.noptmax = 0
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    assert pst.phi < 1.0e-6

    pe = pf.draw(10,use_specsim=True)
    pe.enforce()
    pst.parameter_data.loc[:,"parval1"] = pe.loc[pe.index[0],pst.par_names]
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)


    df = pd.read_csv(os.path.join(pf.new_d,"mult2model_info.csv"), index_col=0)
    arr_pars = df.loc[df.index_cols.isna()].copy()
    model_files = arr_pars.model_file.unique()
    pst.try_parse_name_metadata()
    for model_file in model_files:
        arr = np.loadtxt(os.path.join(pf.new_d,model_file))
        clean_name = model_file.replace(".","_").replace("\\","_").replace("/","_")
        sim_val = pst.res.loc[pst.res.name.apply(lambda x: clean_name in x ),"modelled"]
        sim_val = sim_val.loc[sim_val.index.map(lambda x: "mean_model_file" in x)]
        print(model_file,sim_val,arr.mean())


def xsec_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'xsec')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    shutil.copytree(org_model_ws,tmp_model_ws)

    # SETUP pest stuff...
    nam_file = "10par_xsec.nam"
    os_utils.run("{0} {1}".format(mf_exe_path,nam_file), cwd=tmp_model_ws)

    m = flopy.modflow.Modflow.load(nam_file,model_ws=tmp_model_ws,version="mfnwt")
    sr = m.modelgrid
    t_d = "template_xsec"
    pf = pyemu.utils.PstFrom(tmp_model_ws,t_d,remove_existing=True,spatial_reference=sr)
    pf.add_parameters("hk_Layer_1.ref",par_type="grid",par_style="direct",upper_bound=25,
                      lower_bound=0.25)
    pf.add_parameters("hk_Layer_1.ref", par_type="grid", par_style="multiplier", upper_bound=10.0,
                      lower_bound=0.1)

    hds_arr = np.loadtxt(os.path.join(t_d,"10par_xsec.hds"))
    with open(os.path.join(t_d,"10par_xsec.hds.ins"),'w')  as f:
        f.write("pif ~\n")
        for kper in range(hds_arr.shape[0]):
            f.write("l1 ")
            for j in range(hds_arr.shape[1]):
                oname = "hds_{0}_{1}".format(kper,j)
                f.write(" !{0}! ".format(oname))
            f.write("\n")
    pf.add_observations_from_ins(os.path.join(t_d,"10par_xsec.hds.ins"),pst_path=".")

    pf.mod_sys_cmds.append("mfnwt {0}".format(nam_file))

    pf.build_pst(os.path.join(t_d,"pest.pst"))

    pyemu.os_utils.run("{0} {1}".format(ies_exe_path,"pest.pst"),cwd=t_d)
    pst = pyemu.Pst(os.path.join(t_d,"pest.pst"))
    print(pst.phi)
    assert pst.phi < 1.0e-7


def mf6_freyberg_short_direct_test():

    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from_direct"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external()
    sim.write_simulation()

    # to by pass the issues with flopy
    # shutil.copytree(org_model_ws,tmp_model_ws)
    # sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format("mf6"), cwd=tmp_model_ws)

    template_ws = "new_temp_direct"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=False, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018")
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')

    # Add stream flow observation
    # df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time",
                        use_cols=["GAGE_1","HEADWATER","TAILWATER"],ofile_sep=",")
    # Setup geostruct for spatial pars
    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v, transform="log")
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0, a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {
        "npf_k_": [0.1, 10.],
        "npf_k33_": [.1, 10],
        "sto_ss": [.1, 10],
        "sto_sy": [.9, 1.1],
        "rch_recharge": [.5, 1.5]
    }
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]), unit="d")
    print(dts)
    # setup from array style pars
    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            for arr_file in arr_files:
                nmebase = arr_file.split('.')[1].replace('layer','').replace('_','').replace("npf",'').replace("sto",'').replace("recharge",'')
                # indy direct grid pars for each array type file
                recharge_files = ["recharge_1.txt","recharge_2.txt","recharge_3.txt"]
                pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base="rchg",
                                  pargp="rch_gr", zone_array=ib, upper_bound=1.0e-3, lower_bound=1.0e-7,
                                  par_style="direct")
                # additional constant mults
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file, par_type="constant",
                                  par_name_base=nmebase + "cn",
                                  pargp="rch_const", zone_array=ib, upper_bound=ub, lower_bound=lb,
                                  geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:
            for arr_file in arr_files:
                nmebase = arr_file.split('.')[1].replace(
                    'layer', '').replace('_','').replace("npf",'').replace(
                    "sto",'').replace("recharge",'')
                # grid mults pure and simple
                pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base=nmebase,
                                  pargp=arr_file.split('.')[1] + "_gr", zone_array=ib, upper_bound=ub,
                                  lower_bound=lb,
                                  geostruct=gr_gs)

    # Add a variety of list style pars
    list_files = ["freyberg6.wel_stress_period_data_{0}.txt".format(t)
                  for t in range(1, m.nper + 1)]
    # make dummy versions with headers
    for fl in list_files[0:2]: # this adds a header to well file
        with open(os.path.join(template_ws, fl), 'r') as fr:
            lines = [line for line in fr]
        with open(os.path.join(template_ws, f"new_{fl}"), 'w') as fw:
            fw.write("k i j flx \n")
            for line in lines:
                fw.write(line)




    # fl = "freyberg6.wel_stress_period_data_3.txt" # Add extra string col_id
    for fl in list_files[2:4]:
        with open(os.path.join(template_ws, fl), 'r') as fr:
            lines = [line for line in fr]
        with open(os.path.join(template_ws, f"new_{fl}"), 'w') as fw:
            fw.write("well k i j flx \n")
            for i, line in enumerate(lines):
                fw.write(f"w{i}" + line)


    list_files.sort()
    for list_file in list_files:
        kper = int(list_file.split(".")[1].split('_')[-1]) - 1
        #add spatially constant, but temporally correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="constant", par_name_base="wel{0}".format(kper),
                          pargp="twel_mlt_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=1.5, lower_bound=0.5, datetime=dts[kper], geostruct=rch_temporal_gs)

        # add temporally indep, but spatially correlated wel flux pars
        pf.add_parameters(filenames=list_file, par_type="grid", par_name_base="wel{0}".format(kper),
                          pargp="wel_{0}_direct".format(kper), index_cols=[0, 1, 2], use_cols=[3],
                          upper_bound=0.0, lower_bound=-1000, geostruct=gr_gs, par_style="direct",
                          transform="none")
    # # Adding dummy list pars with different file structures
    list_file = "new_freyberg6.wel_stress_period_data_1.txt"  # with a header
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nw',
                      pargp='nwell_mult', index_cols=['k', 'i', 'j'], use_cols='flx',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs,
                      transform="none")
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nw',
                      pargp='nwell', index_cols=['k', 'i', 'j'], use_cols='flx',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none")
    # with skip instead
    list_file = "new_freyberg6.wel_stress_period_data_2.txt"
    pf.add_parameters(filenames=list_file, par_type="grid", par_name_base='nw',
                      pargp='nwell', index_cols=[0, 1, 2], use_cols=3,
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none", mfile_skip=1)

    list_file = "new_freyberg6.wel_stress_period_data_3.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      pargp='nwell_mult', index_cols=['well', 'k', 'i', 'j'], use_cols='flx',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs,
                      transform="none")
    pf.add_parameters(filenames=list_file, par_type="grid",
                      pargp='nwell', index_cols=['well', 'k', 'i', 'j'], use_cols='flx',
                      upper_bound=10, lower_bound=-10, geostruct=gr_gs, par_style="direct",
                      transform="none")
    # with skip instead
    list_file = "new_freyberg6.wel_stress_period_data_4.txt"
    pf.add_parameters(filenames=list_file, par_type="grid",
                      par_name_base='nw', pargp='nwell',
                      index_cols=[0, 1, 2, 3],  # or... {'well': 0, 'k': 1, 'i': 2, 'j': 3},
                      use_cols=4, upper_bound=10, lower_bound=-10,
                      geostruct=gr_gs, par_style="direct", transform="none",
                      mfile_skip=1)

    list_file = "freyberg6.ghb_stress_period_data_1.txt"
    pf.add_parameters(filenames=list_file, par_type="constant", par_name_base=["ghbst","ghbc"],
                      pargp=["ghb_stage","ghb_cond"], index_cols=[0, 1, 2], use_cols=[3,4],
                      upper_bound=[35,150], lower_bound=[32,50], par_style="direct",
                      transform="none")

    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')
    #cov = pf.build_prior(fmt="non")
    #cov.to_coo("prior.jcb")
    pst.try_parse_name_metadata()
    df = pd.read_csv(os.path.join(tmp_model_ws, "heads.csv"), index_col=0)
    pf.add_observations("heads.csv", insfile="heads.csv.ins", index_cols="time",
                        use_cols=list(df.columns.values),
                        prefix="hds", rebuild_pst=True)

    # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    pst.write_input_files()
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv", chunk_len=1)
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    # TODO Some checks on resultant par files...
    list_files = [f for f in os.listdir('.')
                  if f.startswith('new_') and f.endswith('txt')]
    # check on that those dummy pars compare to the model versions.
    for f in list_files:
        n_df = pd.read_csv(f, sep="\s+")
        o_df = pd.read_csv(f.strip('new_'), sep="\s+", header=None)
        o_df.columns = ['k', 'i', 'j', 'flx']
        assert np.allclose(o_df.values,
                           n_df.loc[:, o_df.columns].values,
                           rtol=1e-4), (
            f"Something broke with alternative style model file: {f}"
        )
    os.chdir(b_d)

    num_reals = 100
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[0], pst.npar_adj)
    assert pe.shape[0] == num_reals

    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","

    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)

    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    assert pst.phi < 0.1, pst.phi


    # turn direct recharge to min and direct wel to min and
    # check that the model results are consistent
    par = pst.parameter_data
    rch_par = par.loc[(par.pname == 'rch') &
                      (par.ptype == 'gr') &
                      (par.pstyle == 'd'),
                      "parnme"]
    wel_par = par.loc[(par.pname.str.contains('wel')) &
                      (par.pstyle == 'd'),
                      "parnme"]
    par.loc[rch_par, "parval1"] = par.loc[rch_par, "parlbnd"]
    # this should set wells to zero since they are negative values in the control file
    par.loc[wel_par, "parval1"] = par.loc[wel_par, "parubnd"]
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    lst = flopy.utils.Mf6ListBudget(os.path.join(pf.new_d, "freyberg6.lst"))
    flx, cum = lst.get_dataframes(diff=True)
    wel_tot = flx.wel.apply(np.abs).sum()
    print(flx.wel)
    assert wel_tot < 1.0e-6, wel_tot

    # shortpars so not going to be able to get ij easily
    # rch_files = [f for f in os.listdir(pf.new_d)
    #              if ".rch_recharge" in f and f.endswith(".txt")]
    # rch_val = par.loc[rch_par,"parval1"][0]
    # i, j = par.loc[rch_par, ["i", 'j']].astype(int).values.T
    # for rch_file in rch_files:
    #     arr = np.loadtxt(os.path.join(pf.new_d, rch_file))[i, j]
    #     print(rch_file, rch_val, arr.mean(), arr.max(), arr.min())
    #     if np.abs(arr.max() - rch_val) > 1.0e-6 or np.abs(arr.min() - rch_val) > 1.0e-6:
    #         raise Exception("recharge too diff")


class TestPstFrom():
    """Test class for some PstFrom functionality
    """
    @classmethod
    def setup(cls):

        # record the original wd
        cls.original_wd = Path().cwd()

        cls.sim_ws = Path('temp/pst-from-small/')
        external_files_folders = [cls.sim_ws / 'external',
                                  cls.sim_ws / '../external_files']
        for folder in external_files_folders:
            folder.mkdir(parents=True, exist_ok=True)

        cls.dest_ws = Path('temp/pst-from-small-template')

        cls.sr = pyemu.helpers.SpatialReference(delr=np.ones(3),
                                            delc=np.ones(3),
                                            rotation=0,
                                            epsg=3070,
                                            xul=0.,
                                            yul=0.,
                                            units='meters',  # gis units of meters?
                                            lenuni=2  # model units of meters
                                            )
        # make some fake external data
        # array data
        cls.array_file = cls.sim_ws / 'hk.dat'
        cls.array_data = np.ones((3, 3))
        np.savetxt(cls.array_file, cls.array_data)
        # list data
        cls.list_file = cls.sim_ws / 'wel.dat'
        cls.list_data = pd.DataFrame({'#k': [1, 1, 1],
                                      'i': [2, 3, 3],
                                      'j': [2, 2, 1],
                                      'flux': [1., 10., 100.]
                                      }, columns=['#k', 'i', 'j', 'flux'])
        cls.list_data.to_csv(cls.list_file, sep=' ', index=False)

        # set up the zones
        zone_array = np.ones((3, 3))  # default of zone 1
        zone_array[2:, 2:] = 0  # position 3, 3 is not parametrized (no zone)
        #zone_array[0, :2] = 2  # 0, 0 and 0, 1 are in zone 2
        zone_array[1, 1] = 2  # 1, 1 is in zone 2
        cls.zone_array = zone_array

        # "geostatistical structure(s)"
        v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
        cls.grid_gs = pyemu.geostats.GeoStruct(variograms=v, transform='log')

        cls.pf = pyemu.utils.PstFrom(original_d=cls.sim_ws, new_d=cls.dest_ws,
                                 remove_existing=True,
                                 longnames=True, spatial_reference=cls.sr,
                                 zero_based=False, tpl_subfolder='tpl')

    def test_add_array_parameters(self):
        """test setting up array parameters with different external file
        configurations and path formats.
        """
        tag = 'hk'
        # test with different array input configurations
        array_file_input = [
            Path('hk0.dat'),  # sim_ws; just file name as Path instance
            'hk1.dat',  # sim_ws; just file name as string
            Path(self.sim_ws, 'hk2.dat'),  # sim_ws; full path as Path instance
            'external/hk3.dat',  # subfolder; relative file path as string
            Path('external/hk4.dat'),  # subfolder; relative path as Path instance
            '../external_files/hk5.dat',  # subfolder up one level
                            ]
        for i, array_file in enumerate(array_file_input):
            par_name_base = f'{tag}_{i:d}'

            # create the file
            # dest_file is the data file relative to the sim or dest ws
            dest_file = Path(array_file)
            if self.sim_ws in dest_file.parents:
                dest_file = dest_file.relative_to(self.sim_ws)
            shutil.copy(self.array_file, Path(self.dest_ws, dest_file))

            self.pf.add_parameters(filenames=array_file, par_type='zone',
                                   zone_array=self.zone_array,
                                   par_name_base=par_name_base,  # basename for parameters that are set up
                                   pargp=f'{tag}_zone',  # Parameter group to assign pars to.
                                   )

            assert (self.dest_ws / dest_file).exists()
            assert (self.dest_ws / f'org/{dest_file.name}').exists()
            # mult file name is par_name_base + `instance` identifier + part_type
            mult_filename = f'{par_name_base}_inst0_zone.csv'
            assert (self.dest_ws / f'mult/{mult_filename}').exists()
            # for now, assume tpl file should be in main folder
            template_file = (self.pf.tpl_d / f'{mult_filename}.tpl')
            assert template_file.exists()

            # make the PEST control file
            pst = self.pf.build_pst()
            assert pst.filename == Path('temp/pst-from-small-template/pst-from-small.pst')
            assert pst.filename.exists()
            rel_tpl = pyemu.utils.pst_from.get_relative_filepath(self.pf.new_d, template_file)
            assert rel_tpl in pst.template_files

            # make the PEST control file (just filename)
            pst = self.pf.build_pst('junk.pst')
            assert pst.filename == Path('temp/pst-from-small-template/junk.pst')
            assert pst.filename.exists()

            # make the PEST control file (file path)
            pst = self.pf.build_pst('temp/pst-from-small-template/junk2.pst')
            assert pst.filename == Path('temp/pst-from-small-template/junk2.pst')
            assert pst.filename.exists()

            # check the mult2model info
            df = pd.read_csv(self.dest_ws / 'mult2model_info.csv')
            # org data file relative to dest_ws
            org_file = Path(df['org_file'].values[i])
            assert org_file == Path(f'org/{dest_file.name}')
            # model file relative to dest_ws
            model_file = Path(df['model_file'].values[i])
            assert model_file == dest_file
            # mult file
            mult_file = Path(df['mlt_file'].values[i])
            assert mult_file == Path(f'mult/{mult_filename}')

            # check applying the parameters (in the dest or template ws)
            os.chdir(self.dest_ws)
            # first delete the model file in the template ws
            model_file.unlink()
            # manually apply a multipler
            mult = 4
            mult_values = np.loadtxt(mult_file)
            mult_values[:] = mult
            np.savetxt(mult_file, mult_values)
            # apply the multiplier
            pyemu.helpers.apply_list_and_array_pars(arr_par_file='mult2model_info.csv')
            # model file should have been remade by apply_list_and_array_pars
            assert model_file.exists()
            result = np.loadtxt(model_file)
            # results should be the same with default multipliers of 1
            # assume details of parameterization are handled by other tests
            assert np.allclose(result, self.array_data * mult)

            # revert to original wd
            os.chdir(self.original_wd)

    def test_add_list_parameters(self):
        """test setting up list parameters with different external file
        configurations and path formats.
        """
        tag = 'wel'
        # test with different array input configurations
        list_file_input = [
            Path('wel0.dat'),  # sim_ws; just file name as Path instance
            'wel1.dat',  # sim_ws; just file name as string
            Path(self.sim_ws, 'wel2.dat'),  # sim_ws; full path as Path instance
            'external/wel3.dat',  # subfolder; relative file path as string
            Path('external/wel4.dat'),  # subfolder; relative path as Path instance
            '../external_files/wel5.dat',  # subfolder up one level
                            ]
        par_type = 'constant'
        for i, list_file in enumerate(list_file_input):
            par_name_base = f'{tag}_{i:d}'

            # create the file
            # dest_file is the data file relative to the sim or dest ws
            dest_file = Path(list_file)
            if self.sim_ws in dest_file.parents:
                dest_file = dest_file.relative_to(self.sim_ws)
            shutil.copy(self.list_file, Path(self.dest_ws, dest_file))

            self.pf.add_parameters(filenames=list_file, par_type=par_type,
                                   par_name_base=par_name_base,
                                   index_cols=[0, 1, 2], use_cols=[3],
                                   pargp=f'{tag}_{i}',
                                   comment_char='#',
                                   )

            assert (self.dest_ws / dest_file).exists()
            assert (self.dest_ws / f'org/{dest_file.name}').exists()
            # mult file name is par_name_base + `instance` identifier + part_type
            mult_filename = f'{par_name_base}_inst0_{par_type}.csv'
            assert (self.dest_ws / f'mult/{mult_filename}').exists()
            # for now, assume tpl file should be in main folder
            template_file = (self.pf.tpl_d / f'{mult_filename}.tpl')
            assert template_file.exists()

            # make the PEST control file
            pst = self.pf.build_pst()
            rel_tpl = pyemu.utils.pst_from.get_relative_filepath(self.pf.new_d, template_file)
            assert rel_tpl in pst.template_files

            # check the mult2model info
            df = pd.read_csv(self.dest_ws / 'mult2model_info.csv')
            # org data file relative to dest_ws
            org_file = Path(df['org_file'].values[i])
            assert org_file == Path(f'org/{dest_file.name}')
            # model file relative to dest_ws
            model_file = Path(df['model_file'].values[i])
            assert model_file == dest_file
            # mult file
            mult_file = Path(df['mlt_file'].values[i])
            assert mult_file == Path(f'mult/{mult_filename}')

            # check applying the parameters (in the dest or template ws)
            os.chdir(self.dest_ws)
            # first delete the model file in the template ws
            model_file.unlink()
            # manually apply a multipler
            mult = 4
            mult_df = pd.read_csv(mult_file)
            # no idea why '3' is the column with multipliers and 'parval1_3' isn't
            # what is the purpose of 'parval1_3'?
            parval_col = '3'
            mult_df[parval_col] = mult
            mult_df.to_csv(mult_file, index=False)
            # apply the multiplier
            pyemu.helpers.apply_list_and_array_pars(arr_par_file='mult2model_info.csv')
            # model file should have been remade by apply_list_and_array_pars
            assert model_file.exists()
            result = pd.read_csv(model_file, delim_whitespace=True)
            # results should be the same with default multipliers of 1
            # assume details of parameterization are handled by other tests
            assert np.allclose(result['flux'], self.list_data['flux'] * mult)

            # revert to original wd
            os.chdir(self.original_wd)
        new_list = self.list_data.copy()
        new_list[['x', 'y']] = new_list[['i', 'j']].apply(
            lambda r: pd.Series(
                [self.pf._spatial_reference.ycentergrid[r.i - 1, r.j - 1],
                 self.pf._spatial_reference.xcentergrid[r.i - 1, r.j - 1]]
            ), axis=1)
        new_list.to_csv(Path(self.dest_ws, "xylist.csv"), index=False, header=False)
        self.pf.add_parameters(filenames="xylist.csv", par_type='grid',
                               par_name_base="xywel",
                               index_cols={'lay': 0, 'x': 4, 'y': 5},
                               use_cols=[3],
                               pargp=f'xywel',
                               geostruct=self.grid_gs,
                               rebuild_pst=True
                               )
        cov = self.pf.build_prior()
        x = cov.as_2d[-3:, -3:]
        assert np.count_nonzero(x - np.diag(np.diagonal(x))) == 6
        assert np.sum(x < np.diag(x)) == 6


    def test_add_array_parameters_pps_grid(self):
        """test setting up array parameters with a list of array text
        files in a subfolder.
        """
        tag = 'hk'
        par_styles = ['multiplier', #'direct'
                      ]
        array_files = ['hk_{}_{}.dat', 'external/hk_{}_{}.dat']
        for par_style in par_styles:
            mult2model_row = 0
            for j, array_file in enumerate(array_files):

                par_types = {'pilotpoints': 'pp',
                             'grid': 'gr'}
                for i, (par_type, suffix) in enumerate(par_types.items()):
                    # (re)create the file
                    dest_file = array_file.format(mult2model_row, suffix)
                    shutil.copy(self.array_file, Path(self.dest_ws, dest_file))
                    # add the parameters
                    par_name_base = f'{tag}_{suffix}'
                    self.pf.add_parameters(filenames=dest_file, par_type=par_type,
                                           zone_array=self.zone_array,
                                           par_name_base=par_name_base,
                                           pargp=f'{tag}_zone',
                                           pp_space=1, geostruct=self.grid_gs,
                                           par_style=par_style
                                           )
                    if par_type != 'pilotpoints':
                        template_file = (self.pf.tpl_d / f'{par_name_base}_inst0_grid.csv.tpl')
                        assert template_file.exists()
                    else:
                        template_file = (self.pf.tpl_d / f'{par_name_base}_inst0pp.dat.tpl')
                        assert template_file.exists()

                    # make the PEST control file
                    pst = self.pf.build_pst()
                    rel_tpl = pyemu.utils.pst_from.get_relative_filepath(self.pf.new_d, template_file)
                    assert rel_tpl in pst.template_files

                    # check the mult2model info
                    df = pd.read_csv(self.dest_ws / 'mult2model_info.csv')
                    mult_file = Path(df['mlt_file'].values[mult2model_row])

                    # check applying the parameters (in the dest or template ws)
                    os.chdir(self.dest_ws)
                    # first delete the model file in the template ws
                    model_file = df['model_file'].values[mult2model_row]
                    os.remove(model_file)
                    # manually apply a multipler
                    mult = 4
                    if par_type != "pilotpoints":
                        mult_values = np.loadtxt(mult_file)
                        mult_values[:] = mult
                        np.savetxt(mult_file, mult_values)
                    else:
                        ppdata = pp_file_to_dataframe(df['pp_file'].values[mult2model_row])
                        ppdata['parval1'] = mult
                        write_pp_file(df['pp_file'].values[mult2model_row], ppdata)
                    # apply the multiplier
                    pyemu.helpers.apply_list_and_array_pars(arr_par_file='mult2model_info.csv')
                    # model files should have been remade by apply_list_and_array_pars
                    for model_file in df['model_file']:
                        assert os.path.exists(model_file)
                        result = np.loadtxt(model_file)
                        # results should be the same with default multipliers of 1
                        # assume details of parameterization are handled by other tests

                        # not sure why zone 2 is coming back as invalid (1e30)
                        zone1 = self.zone_array == 1
                        assert np.allclose(result[zone1], self.array_data[zone1] * mult)

                    # revert to original wd
                    os.chdir(self.original_wd)
                    mult2model_row += 1

    def test_add_direct_array_parameters(self):
        """test setting up array parameters with a list of array text
        files in a subfolder.
        """
        tag = 'hk'
        par_styles = ['direct', #'direct'
                      ]
        array_files = ['hk_{}_{}.dat', 'external/hk_{}_{}.dat']
        for par_style in par_styles:
            mult2model_row = 0
            for j, array_file in enumerate(array_files):

                par_types = {#'constant': 'cn',
                             'zone': 'zn',
                             'grid': 'gr'}
                for i, (par_type, suffix) in enumerate(par_types.items()):
                    # (re)create the file
                    dest_file = array_file.format(mult2model_row, suffix)

                    # make a new input array file with initial values
                    arr = np.loadtxt(self.array_file)
                    parval = 8
                    arr[:] = parval
                    np.savetxt(Path(self.dest_ws, dest_file), arr)

                    # add the parameters
                    par_name_base = f'{tag}_{suffix}'
                    self.pf.add_parameters(filenames=dest_file, par_type=par_type,
                                           zone_array=self.zone_array,
                                           par_name_base=par_name_base,
                                           pargp=f'{tag}_zone',
                                           par_style=par_style
                                           )
                    template_file = (self.pf.tpl_d / f'{Path(dest_file).name}.tpl')
                    assert template_file.exists()

                    # make the PEST control file
                    pst = self.pf.build_pst()
                    rel_tpl = pyemu.utils.pst_from.get_relative_filepath(self.pf.new_d, template_file)
                    assert rel_tpl in pst.template_files

                    # check the mult2model info
                    df = pd.read_csv(self.dest_ws / 'mult2model_info.csv')

                    # check applying the parameters (in the dest or template ws)
                    os.chdir(self.dest_ws)

                    # first delete the model file that was in the template ws
                    model_file = df['model_file'].values[mult2model_row]
                    assert Path(model_file) == Path(dest_file), (f"model_file: {model_file} "
                                                     f"differs from dest_file {dest_file}")
                    os.remove(model_file)

                    # pretend that PEST created the input files
                    # values from dest_file above formed basis for parval in PEST control data
                    # PEST input file is set up as the org/ version
                    # apply_list_and_array_pars then takes the org/ version and writes model_file
                    np.savetxt(pst.input_files[mult2model_row], arr)

                    pyemu.helpers.apply_list_and_array_pars(arr_par_file='mult2model_info.csv')
                    # model files should have been remade by apply_list_and_array_pars
                    for model_file in df['model_file']:
                        assert os.path.exists(model_file)
                        result = np.loadtxt(model_file)
                        # results should be the same with default multipliers of 1
                        # assume details of parameterization are handled by other tests

                        # not sure why zone 2 is coming back as invalid (1e30)
                        zone1 = self.zone_array == 1
                        assert np.allclose(result[zone1], parval)

                    # revert to original wd
                    os.chdir(self.original_wd)
                    mult2model_row += 1

    def test_add_array_parameters_to_file_list(self):
        """test setting up array parameters with a list of array text
        files in a subfolder.
        """
        tag = 'r'
        array_file_input = ['external/r0.dat',
                            'external/r1.dat',
                            'external/r2.dat']
        for file in array_file_input:
            shutil.copy(self.array_file, Path(self.dest_ws, file))

        # single 2D zone array applied to each file in filesnames
        self.pf.add_parameters(filenames=array_file_input, par_type='zone',
                               zone_array=self.zone_array,
                               par_name_base=tag,  # basename for parameters that are set up
                               pargp=f'{tag}_zone',  # Parameter group to assign pars to.
                               )
        # make the PEST control file
        pst = self.pf.build_pst()
        # check the mult2model info
        df = pd.read_csv(self.dest_ws / 'mult2model_info.csv')
        mult_file = Path(df['mlt_file'].values[0])

        # check applying the parameters (in the dest or template ws)
        os.chdir(self.dest_ws)
        # first delete the model file in the template ws
        for model_file in df['model_file']:
            os.remove(model_file)
        # manually apply a multipler
        mult = 4
        mult_values = np.loadtxt(mult_file)
        mult_values[:] = mult
        np.savetxt(mult_file, mult_values)
        # apply the multiplier
        pyemu.helpers.apply_list_and_array_pars(arr_par_file='mult2model_info.csv')
        # model files should have been remade by apply_list_and_array_pars
        for model_file in df['model_file']:
            assert os.path.exists(model_file)
            result = np.loadtxt(model_file)
            # results should be the same with default multipliers of 1
            # assume details of parameterization are handled by other tests
            assert np.allclose(result, self.array_data * mult)

        # revert to original wd
        os.chdir(self.original_wd)

    def test_add_array_parameters_alt_inst_str_none_m(self):
        """Given a list of text file arrays, test setting up
        array parameters that can extend across multiple files,
        but have a different multiplier file for each text array.
        For example, if the same zones are present in each layer of a model, 
        but have different configurations in each layer
        (such that a different zone array is needed for each layer).
        
        Test alt_inst_str=None and par_style="multiplier"
        
        TODO: switch to pytest so that we could simply use one function 
        for this with multiple parameters
        """
        tag = 'r'
        array_file_input = ['external/r0.dat',
                            'external/r1.dat',
                            'external/r2.dat']
        for file in array_file_input:
            shutil.copy(self.array_file, Path(self.dest_ws, file))
        for array_file in array_file_input:
            self.pf.add_parameters(filenames=array_file, par_type='zone',
                                    par_style="multiplier",
                                    zone_array=self.zone_array,
                                    par_name_base=tag,  # basename for parameters that are set up
                                    pargp=f'{tag}_zone',  # Parameter group to assign pars to.
                                    alt_inst_str=None
                                    )
        pst = self.pf.build_pst()
        # the parameter data section should have
        # only 2 parameters, for zones 1 and 2
        parzones = sorted(pst.parameter_data.zone.astype(float).astype(int).tolist())
        assert parzones == [1, 2]
        assert len(pst.template_files) == 3
        assert len(self.pf.mult_files) == 3
        
    def test_add_array_parameters_alt_inst_str_0_d(self):
        """Given a list of text file arrays, test setting up
        array parameters that can extend across multiple files,
        but have a different multiplier file for each text array.
        For example, if the same zones are present in each layer of a model, 
        but have different configurations in each layer
        (such that a different zone array is needed for each layer).
        
        Test alt_inst_str="" and par_style="direct"
        """
        tag = 'r'
        array_file_input = ['external/r0.dat',
                            'external/r1.dat',
                            'external/r2.dat']
        for file in array_file_input:
            shutil.copy(self.array_file, Path(self.dest_ws, file))
        # test both None and "" for alt_inst_str
        for array_file in array_file_input:
            self.pf.add_parameters(filenames=array_file, par_type='zone',
                                    par_style="direct",
                                    zone_array=self.zone_array,
                                    par_name_base=tag,  # basename for parameters that are set up
                                    pargp=f'{tag}_zone',  # Parameter group to assign pars to.
                                    alt_inst_str=""
                                    )
        pst = self.pf.build_pst()
        # the parameter data section should have
        # only 2 parameters, for zones 1 and 2
        parzones = sorted(pst.parameter_data.zone.astype(float).astype(int).tolist())
        assert parzones == [1, 2]
        assert len(pst.template_files) == 3

    @classmethod
    def teardown(cls):
        # cleanup
        os.chdir(cls.original_wd)
        shutil.rmtree(cls.sim_ws / '../external_files')
        shutil.rmtree(cls.sim_ws)
        shutil.rmtree(cls.dest_ws)


def test_get_filepath():
    from pyemu.utils.pst_from import get_filepath

    input_expected = [(('folder', 'file.txt'), Path('folder/file.txt')),
                      ((Path('folder'), 'file.txt'), Path('folder/file.txt')),
                      (('folder', Path('file.txt')), Path('folder/file.txt')),
                      ((Path('folder'), Path('file.txt')), Path('folder/file.txt')),
                      ]
    for input, expected in input_expected:
        result = get_filepath(*input)
        assert result == expected


def invest():
    import os
    import pyemu

    i = pyemu.pst_utils.InstructionFile(os.path.join("new_temp","freyberg.sfo.dat.ins"))
    i.read_output_file(os.path.join("new_temp","freyberg.sfo.dat"))


def pstfrom_profile():
    import cProfile
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join("..", "examples", "freyberg_sfr_update")
    nam_file = "freyberg.nam"
    m = flopy.modflow.Modflow.load(nam_file, model_ws=org_model_ws,
                                   check=False, forgive=False,
                                   exe_name=mf_exe_path)
    flopy.modflow.ModflowRiv(m, stress_period_data={
        0: [[0, 0, 0, m.dis.top.array[0, 0], 1.0, m.dis.botm.array[0, 0, 0]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]],
            [0, 0, 1, m.dis.top.array[0, 1], 1.0, m.dis.botm.array[0, 0, 1]]]})

    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    m.external_path = "."
    m.change_model_ws(tmp_model_ws)
    m.write_input()
    print("{0} {1}".format(mf_exe_path, m.name + ".nam"), tmp_model_ws)
    os_utils.run("{0} {1}".format(mf_exe_path, m.name + ".nam"),
                 cwd=tmp_model_ws)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    sr = pyemu.helpers.SpatialReference.from_namfile(
        os.path.join(m.model_ws, m.namefile),
        delr=m.dis.delr, delc=m.dis.delc)
    # set up PstFrom object
    shutil.copy(os.path.join(org_model_ws, 'ucn.csv'),
                os.path.join(tmp_model_ws, 'ucn.csv'))
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False)
    # obs
    pr = cProfile.Profile()
    pr.enable()
    pf.add_observations('ucn.csv', insfile=None,
                        index_cols=['t', 'k', 'i', 'j'],
                        use_cols=["ucn"], prefix=['ucn'],
                        ofile_sep=',', obsgp=['ucn'])
    pr.disable()

    # pars
    pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
                      index_cols=[0, 1, 2], use_cols=[3, 5],
                      par_name_base=["rivstage_grid", "rivbot_grid"],
                      mfile_fmt='%10d%10d%10d %15.8F %15.8F %15.8F',
                      pargp='rivbot')
    # pf.add_parameters(filenames="RIV_0000.dat", par_type="grid",
    #                   index_cols=[0, 1, 2], use_cols=4)
    # pf.add_parameters(filenames=["WEL_0000.dat", "WEL_0001.dat"],
    #                   par_type="grid", index_cols=[0, 1, 2], use_cols=3,
    #                   par_name_base="welflux_grid",
    #                   zone_array=m.bas6.ibound.array)
    # pf.add_parameters(filenames=["WEL_0000.dat"], par_type="constant",
    #                   index_cols=[0, 1, 2], use_cols=3,
    #                   par_name_base=["flux_const"])
    # pf.add_parameters(filenames="rech_1.ref", par_type="grid",
    #                   zone_array=m.bas6.ibound[0].array,
    #                   par_name_base="rch_datetime:1-1-1970")
    # pf.add_parameters(filenames=["rech_1.ref", "rech_2.ref"],
    #                   par_type="zone", zone_array=m.bas6.ibound[0].array)
    # pf.add_parameters(filenames="rech_1.ref", par_type="pilot_point",
    #                   zone_array=m.bas6.ibound[0].array,
    #                   par_name_base="rch_datetime:1-1-1970", pp_space=4)
    # pf.add_parameters(filenames="rech_1.ref", par_type="pilot_point",
    #                   zone_array=m.bas6.ibound[0].array,
    #                   par_name_base="rch_datetime:1-1-1970", pp_space=1,
    #                   ult_ubound=100, ult_lbound=0.0)
    #
    # # add model run command
    # pf.mod_sys_cmds.append("{0} {1}".format(mf_exe_name, m.name + ".nam"))
    # print(pf.mult_files)
    # print(pf.org_files)
    #
    # # build pest
    # pst = pf.build_pst('freyberg.pst')
    #
    # # check mult files are in pst input files
    # csv = os.path.join(template_ws, "mult2model_info.csv")
    # df = pd.read_csv(csv, index_col=0)
    # pst_input_files = {str(f) for f in pst.input_files}
    # mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
    #                             pst_input_files) -
    #                            set(df.loc[df.pp_file.notna()].mlt_file))
    # assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)
    #
    # pst.write_input_files(pst_path=pf.new_d)
    # # test par mults are working
    # b_d = os.getcwd()
    # os.chdir(pf.new_d)
    # try:
    #     pyemu.helpers.apply_list_and_array_pars(
    #         arr_par_file="mult2model_info.csv")
    # except Exception as e:
    #     os.chdir(b_d)
    #     raise Exception(str(e))
    # os.chdir(b_d)
    #
    # pst.control_data.noptmax = 0
    # pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    # pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    #
    # res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    # assert os.path.exists(res_file), res_file
    # pst.set_res(res_file)
    # print(pst.phi)
    # assert pst.phi < 1.0e-5, pst.phi
    pr.print_stats(sort="cumtime")


def mf6_freyberg_arr_obs_and_headerless_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    # to by pass the issues with flopy
    # shutil.copytree(org_model_ws,tmp_model_ws)
    # sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # m = sim.get_model("freyberg6")

    # SETUP pest stuff...
    os_utils.run("{0} ".format(mf6_exe_path), cwd=tmp_model_ws)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    # sr = pyemu.helpers.SpatialReference.from_namfile(
    #     os.path.join(tmp_model_ws, "freyberg6.nam"),
    #     delr=m.dis.delr.array, delc=m.dis.delc.array)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018")

    list_file = "freyberg6.wel_stress_period_data_1.txt"
    df = pd.read_csv(os.path.join(template_ws,list_file),header=None,delim_whitespace=True)
    df.loc[:,4] = 4
    df.loc[:,5] = 5
    df.to_csv(os.path.join(template_ws,list_file),sep=" ",index=False,header=False)
    pf.add_observations(list_file, index_cols=[0, 1, 2], use_cols=[3,5], ofile_skip=0, includes_header=False,
                        prefix="welobs")

    with open(os.path.join(template_ws,"badlistcall.txt"), "w") as fp:
        fp.write("this is actually a header\n")
        fp.write("entry 0 10 100.4 2\n")
        fp.write("entry 1 10 2.4 5.0")
    pf.add_observations("badlistcall.txt", index_cols=[0, 1], use_cols=[3, 4],
                        ofile_skip=0, includes_header=False,
                        prefix="badlistcall")


    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0, a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_": [0.1, 10.]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]), unit="d")
    print(dts)
    arr_dict = {}
    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        for arr_file in arr_files:
            #pf.add_parameters(filenames=arr_file, par_type="grid", par_name_base=arr_file.split('.')[1] + "_gr",
            #                  pargp=arr_file.split('.')[1] + "_gr", zone_array=ib, upper_bound=ub, lower_bound=lb,
            #                  geostruct=gr_gs)
            pf.add_parameters(filenames=arr_file, par_type="constant", par_name_base=arr_file.split('.')[1] + "_cn",
                              pargp=arr_file.split('.')[1] + "_cn", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              transform="fixed")
            pf.add_parameters(filenames=arr_file, par_type="constant", par_name_base=arr_file.split('.')[1] + "_cn",
                              pargp=arr_file.split('.')[1] + "_cn", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              transform="log")


            pf.add_observations(arr_file,zone_array=ib)
            arr_dict[arr_file] = np.loadtxt(pf.new_d / arr_file)



    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)



    # build pest
    pst = pf.build_pst('freyberg.pst')
    pe = pf.draw(100,use_specsim=True)
    cov = pf.build_prior()
    scnames = set(cov.row_names)
    print(pst.npar_adj,pst.npar,pe.shape)
    par = pst.parameter_data
    fpar = set(par.loc[par.partrans=="fixed","parnme"].tolist())
    spe = set(list(pe.columns))
    assert len(fpar.intersection(spe)) == 0,str(fpar.intersection(spe))
    assert len(fpar.intersection(scnames)) == 0, str(fpar.intersection(scnames))
    pst.try_parse_name_metadata()
    obs = pst.observation_data
    for fname,arr in arr_dict.items():

        fobs = obs.loc[obs.obsnme.str.contains(Path(fname).stem), :]
        #print(fobs)
        fobs = fobs.astype({c: int for c in ['i', 'j']})

        pval = fobs.loc[fobs.apply(lambda x: x.i==3 and x.j==1,axis=1),"obsval"]
        assert len(pval) == 1
        pval = pval[0]
        aval = arr[3,1]
        print(fname,pval,aval)
        assert pval == aval,"{0},{1},{2}".format(fname,pval,aval)

    df = pd.read_csv(os.path.join(template_ws,list_file),header=None,delim_whitespace=True)
    print(df)
    wobs = obs.loc[obs.obsnme.str.contains("welobs"),:]
    print(wobs)
    fvals = df.iloc[:,3]
    pvals = wobs.loc[:,"obsval"].iloc[:df.shape[0]]
    d = fvals.values - pvals.values
    print(d)
    assert d.sum() == 0
    fvals = df.iloc[:, 5]
    pvals = wobs.loc[:, "obsval"].iloc[df.shape[0]:]
    d = fvals.values - pvals.values
    print(d)
    assert d.sum() == 0


def mf6_freyberg_pp_locs_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    # SETUP pest stuff...
    os_utils.run("{0} ".format(mf6_exe_path), cwd=tmp_model_ws)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018",
                 chunk_len=1)

    # pf.post_py_cmds.append("generic_function()")
    df = pd.read_csv(os.path.join(tmp_model_ws, "sfr.csv"), index_col=0)
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols="time", use_cols=list(df.columns.values))
    v = pyemu.geostats.ExpVario(contribution=1.0, a=5000)
    pp_gs = pyemu.geostats.GeoStruct(variograms=v)
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_": [0.1, 10.]}#, "npf_k33_": [.1, 10], "sto_ss": [.1, 10], "sto_sy": [.9, 1.1],
    #         "rch_recharge": [.5, 1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]), unit="d")
    print(dts)

    xmn = m.modelgrid.xvertices.min()
    xmx = m.modelgrid.xvertices.max()
    ymn = m.modelgrid.yvertices.min()
    ymx = m.modelgrid.yvertices.max()

    numpp = 20
    xvals = np.random.uniform(xmn,xmx,numpp)
    yvals = np.random.uniform(ymn, ymx, numpp)
    pp_locs = pd.DataFrame({"x":xvals,"y":yvals})
    pp_locs.loc[:,"zone"] = 1
    pp_locs.loc[:,"name"] = ["pp_{0}".format(i) for i in range(numpp)]
    pp_locs.loc[:,"parval1"] = 1.0

    pyemu.pp_utils.write_pp_shapfile(pp_locs,os.path.join(template_ws,"pp_locs.shp"))
    df = pyemu.pp_utils.pilot_points_from_shapefile(os.path.join(template_ws,"pp_locs.shp"))

    #pp_locs = pyemu.pp_utils.setup_pilotpoints_grid(sr=sr,prefix_dict={0:"pps_1"})
    #pp_locs = pp_locs.loc[:,["name","x","y","zone","parval1"]]
    pp_locs.to_csv(os.path.join(template_ws,"pp.csv"))
    pyemu.pp_utils.write_pp_file(os.path.join(template_ws,"pp_file.dat"),pp_locs)
    pp_container = ["pp_file.dat","pp.csv","pp_locs.shp"]

    for tag, bnd in tags.items():
        lb, ub = bnd[0], bnd[1]
        arr_files = [f for f in os.listdir(tmp_model_ws) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            pass
            # pf.add_parameters(filenames=arr_files, par_type="grid", par_name_base="rch_gr",
            #                   pargp="rch_gr", zone_array=ib, upper_bound=ub, lower_bound=lb,
            #                   geostruct=gr_gs)
            # for arr_file in arr_files:
            #     kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
            #     pf.add_parameters(filenames=arr_file, par_type="constant", par_name_base=arr_file.split('.')[1] + "_cn",
            #                       pargp="rch_const", zone_array=ib, upper_bound=ub, lower_bound=lb,
            #                       geostruct=rch_temporal_gs,
            #                       datetime=dts[kper])
        else:
            for i,arr_file in enumerate(arr_files):
                if i < len(pp_container):
                    pp_opt = pp_container[i]
                else:
                    pp_opt = pp_locs
                pf.add_parameters(filenames=arr_file, par_type="pilotpoints",
                                  par_name_base=arr_file.split('.')[1] + "_pp",
                                  pargp=arr_file.split('.')[1] + "_pp", zone_array=ib,
                                  upper_bound=ub, lower_bound=lb,pp_space=pp_opt)



    # add model run command
    pf.mod_sys_cmds.append("mf6")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')

    num_reals = 10
    pe = pf.draw(num_reals, use_specsim=True)
    pe.to_binary(os.path.join(template_ws, "prior.jcb"))

    pst.parameter_data.loc[:,"partrans"] = "fixed"
    pst.parameter_data.loc[::10, "partrans"] = "log"
    pst.control_data.noptmax = -1
    pst.write(os.path.join(template_ws,"freyberg.pst"))

    #pyemu.os_utils.run("{0} freyberg.pst".format("pestpp-glm"),cwd=template_ws)
    pyemu.os_utils.start_workers(template_ws,pp_exe_path,"freyberg.pst",num_workers=5,worker_root=".",master_dir="master_glm")

    sen_df = pd.read_csv(os.path.join("master_glm","freyberg.isen"),index_col=0).loc[:,pst.adj_par_names]
    print(sen_df.T)
    mn = sen_df.values.min()
    print(mn)
    assert mn > 0.0


def usg_freyberg_test():
    import numpy as np
    import pandas as pd
    import flopy
    import pyemu
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    #path to org model files
    org_model_ws = os.path.join('..', 'examples', 'freyberg_usg')
    # flopy is not liking the rch package in unstruct, so allow it to fail and keep going...
    m = flopy.mfusg.MfUsg.load("freyberg.usg.nam", model_ws=org_model_ws,
                               verbose=True, forgive=True, check=False)

    #convert to all open/close
    m.external_path = "."
    tmp_model_ws = "temp_pst_from_usg"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    #change dir and write
    m.change_model_ws(tmp_model_ws, reset_external=True)
    m.write_input()

    nam_file = os.path.join(tmp_model_ws,"freyberg.usg.nam")

    #make sure the model runs in the new dir with all external formats
    pyemu.os_utils.run("mfusg freyberg.usg.nam", cwd=tmp_model_ws)

    # for usg, we need to do some trickery to support the unstructured by layers concept
    # this is just for array-based parameters, list-based pars are g2g because they have an index
    gsf = pyemu.gw_utils.GsfReader(os.path.join(org_model_ws,"freyberg.usg.gsf"))
    df = gsf.get_node_data()
    df.loc[:,"xy"] = df.apply(lambda x: (x.x, x.y),axis=1)
    # these need to be zero based since they are with zero-based array indices later...
    df.loc[:,"node"] -= 1
    # process each layer
    layers = df.layer.unique()
    layers.sort()
    sr_dict_by_layer = {}
    for layer in layers:
        df_lay = df.loc[df.layer==layer,:].copy()
        df_lay.sort_values(by="node")
        #substract off the min node number so that each layers node dict starts at zero
        df_lay.loc[:,"node"] = df_lay.node - df_lay.node.min()
        print(df_lay)
        srd = {n:xy for n,xy in zip(df_lay.node.values,df_lay.xy.values)}
        sr_dict_by_layer[layer] = srd

    # gen up a fake zone array
    zone_array_k0 = np.ones((1, len(sr_dict_by_layer[1])))
    zone_array_k0[:, 200:420] = 2
    zone_array_k0[:, 600:1000] = 3

    zone_array_k2 = np.ones((1, len(sr_dict_by_layer[3])))
    zone_array_k2[:, 200:420] = 2
    zone_array_k2[:, 500:1000:3] = 3
    zone_array_k2[:,:100] = 0

    #gen up some fake pp locs
    np.random.seed(pyemu.en.SEED)
    num_pp = 20
    data = {"name":[],"x":[],"y":[],"zone":[]}
    visited = set()
    for i in range(num_pp):
        while True:
            idx = np.random.randint(0,len(sr_dict_by_layer[1]))
            if idx  not in visited:
                break
        x,y = sr_dict_by_layer[1][idx]
        data["name"].append("pp_{0}".format(i))
        data["x"].append(x)
        data["y"].append(y)
        data["zone"].append(zone_array_k2[0,idx])
        visited.add(idx)
    # harded coded to get a zone 3 pp
    idx = 500
    assert zone_array_k2[0,idx] == 3,zone_array_k2[0,idx]

    x, y = sr_dict_by_layer[1][idx]
    data["name"].append("pp_{0}".format(i+1))
    data["x"].append(x)
    data["y"].append(y)
    data["zone"].append(zone_array_k2[0, idx])
    pp_df = pd.DataFrame(data=data,index=data["name"])

    # a geostruct that describes spatial continuity for properties
    # this is used for all props and for both grid and pilot point
    # pars cause Im lazy...
    v = pyemu.geostats.ExpVario(contribution=1.0,a=500)
    gs = pyemu.geostats.GeoStruct(variograms=v)

    # we pass the full listing of node coord info to the constructor for use
    # with list-type parameters
    pf = pyemu.utils.PstFrom(tmp_model_ws,"template",longnames=True,remove_existing=True,
                             zero_based=False,spatial_reference=gsf.get_node_coordinates(zero_based=True))

    pf.add_parameters("hk_Layer_3.ref", par_type="pilotpoints",
                      par_name_base="hk3_pp", pp_space=pp_df,
                      geostruct=gs, spatial_reference=sr_dict_by_layer[3],
                      upper_bound=2.0, lower_bound=0.5,
                      zone_array=zone_array_k2)

    # we pass layer specific sr dict for each "array" type that is spatially distributed
    pf.add_parameters("hk_Layer_1.ref",par_type="grid",par_name_base="hk1_Gr",geostruct=gs,
                      spatial_reference=sr_dict_by_layer[1],
                      upper_bound=2.0,lower_bound=0.5)
    pf.add_parameters("sy_Layer_1.ref", par_type="zone", par_name_base="sy1_zn",zone_array=zone_array_k0,
                      upper_bound=1.5,lower_bound=0.5,ult_ubound=0.35)



    # add a multiplier par for each well for each stress period
    wel_files = [f for f in os.listdir(tmp_model_ws) if f.lower().startswith("wel_") and f.lower().endswith(".dat")]
    for wel_file in wel_files:
        pf.add_parameters(wel_file,par_type="grid",par_name_base=wel_file.lower().split('.')[0],index_cols=[0],use_cols=[1],
                          geostruct=gs,lower_bound=0.5,upper_bound=1.5)

    # add pest "observations" for each active node for each stress period
    hds_runline, df = pyemu.gw_utils.setup_hds_obs(
        os.path.join(pf.new_d, "freyberg.usg.hds"), kperk_pairs=None,
        prefix="hds", include_path=False, text="headu", skip=-1.0e+30)
    pf.add_observations_from_ins(os.path.join(pf.new_d, "freyberg.usg.hds.dat.ins"), pst_path=".")
    pf.post_py_cmds.append(hds_runline)

    # the command the run the model
    pf.mod_sys_cmds.append("mfusg freyberg.usg.nam")

    #build the control file and draw the prior par ensemble
    pf.build_pst()
    pst = pf.pst
    par = pst.parameter_data

    gr_hk_pars = par.loc[par.parnme.str.contains("hk1_gr"),"parnme"]
    pf.pst.parameter_data.loc[gr_hk_pars,"parubnd"] = np.random.random(gr_hk_pars.shape[0]) * 5
    pf.pst.parameter_data.loc[gr_hk_pars, "parlbnd"] = np.random.random(gr_hk_pars.shape[0]) * 0.2
    pe = pf.draw(num_reals=100)
    pe.enforce()
    pe.to_csv(os.path.join(pf.new_d,"prior.csv"))
    cov = pf.build_prior(filename=None)
    #make sure the prior cov has off diagonals
    cov = pf.build_prior(sigma_range=6)
    covx = cov.x.copy()
    covx[np.abs(covx)>1.0e-7] = 1.0
    assert covx.sum() > pf.pst.npar_adj + 1
    dcov = pyemu.Cov.from_parameter_data(pf.pst,sigma_range=6)
    dcov = dcov.get(cov.row_names)
    diag = np.diag(cov.x)
    diff = np.abs(diag.flatten() - dcov.x.flatten())
    print(diag)
    print(dcov.x)
    print(diff)
    print(diff.max())
    assert diff.max() < 1.0e-6

    # test that the arr hds obs process is working
    os.chdir(pf.new_d)
    pyemu.gw_utils.apply_hds_obs('freyberg.usg.hds', precision='single', text='headu')
    os.chdir("..")

    # run the full process once using the initial par values in the control file
    # since we are using only multipliers, the initial values are all 1's so
    # the phi should be pretty close to zero
    pf.pst.control_data.noptmax = 0
    pf.pst.write(os.path.join(pf.new_d,"freyberg.usg.pst"),version=2)
    pyemu.os_utils.run("{0} freyberg.usg.pst".format(ies_exe_path),cwd=pf.new_d)
    pst = pyemu.Pst(os.path.join(pf.new_d,"freyberg.usg.pst"))
    assert pst.phi < 1.e-3

    #make sure the processed model input arrays are veru similar to the org arrays (again 1s for mults)
    for arr_file in ["hk_Layer_1.ref","hk_Layer_3.ref"]:
        in_arr = np.loadtxt(os.path.join(pf.new_d,arr_file))
        org_arr = np.loadtxt(os.path.join(pf.new_d,"org",arr_file))
        d = np.abs(in_arr - org_arr)
        print(d.sum())
        assert d.sum() < 1.0e-3,arr_file

    # now run a random realization from the prior par en and make sure things have changed
    pst.parameter_data.loc[pe.columns,"parval1"] = pe.iloc[0,:].values
    pst.write(os.path.join(pf.new_d, "freyberg.usg.pst"), version=2)
    pyemu.os_utils.run("{0} freyberg.usg.pst".format(ies_exe_path), cwd=pf.new_d)

    pst = pyemu.Pst(os.path.join(pf.new_d, "freyberg.usg.pst"))
    assert pst.phi > 1.0e-3,pst.phi

    for arr_file in ["hk_Layer_1.ref", "hk_Layer_3.ref"]:
        in_arr = np.loadtxt(os.path.join(pf.new_d, arr_file))
        org_arr = np.loadtxt(os.path.join(pf.new_d, "org", arr_file))
        d = np.abs(in_arr - org_arr)
        print(d.sum())
        assert d.sum() > 1.0e-3, arr_file

    # check that the pilot point process is respecting the zone array
    par = pst.parameter_data
    pp_par = par.loc[par.parnme.str.contains("pp"),:]
    pst.parameter_data.loc[pp_par.parnme,"parval1"] = pp_par.zone.apply(np.float64)
    pst.control_data.noptmax = 0
    pst.write(os.path.join(pf.new_d,"freyberg.usg.pst"),version=2)
    #pst.write_input_files(pf.new_d)
    pyemu.os_utils.run("{0} freyberg.usg.pst".format(ies_exe_path), cwd=pf.new_d)
    arr = np.loadtxt(os.path.join(pf.new_d,"mult","hk3_pp_inst0_pilotpoints.csv"))
    arr[zone_array_k2[0,:]==0] = 0
    d = np.abs(arr - zone_array_k2)
    print(d)
    print(d.sum())
    assert d.sum() == 0.0,d.sum()

def mf6_add_various_obs_test():
    import flopy
    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp_model_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    # SETUP pest stuff...
    os_utils.run("{0} ".format(mf6_exe_path), cwd=tmp_model_ws)

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False, start_datetime="1-1-2018",
                 chunk_len=1)

    # blind obs add
    pf.add_observations("sfr.csv", insfile="sfr.csv.ins", index_cols='time',
                        ofile_sep=',')
    pf.add_observations("heads.csv", index_cols=0, obsgp='hds')
    pf.add_observations("freyberg6.npf_k_layer1.txt",
                        obsgp='hk1', zone_array=m.dis.idomain.array[0])
    pf.add_observations("freyberg6.npf_k_layer2.txt",
                        zone_array=m.dis.idomain.array[0],
                        prefix='lay2k')
    pf.add_observations("freyberg6.npf_k_layer3.txt",
                        zone_array=m.dis.idomain.array[0])

    linelen = 10000
    _add_big_obsffile(pf, profile=True, nchar=linelen)

    # TODO more variations on the theme
    # add single par so we can run
    pf.add_parameters(["freyberg6.npf_k_layer1.txt",
                       "freyberg6.npf_k_layer2.txt",
                       "freyberg6.npf_k_layer3.txt"],par_type='constant')
    pf.mod_sys_cmds.append("mf6")
    pf.add_py_function(
        'pst_from_tests.py',
        f"_add_big_obsffile('.', profile=False, nchar={linelen})",
        is_pre_cmd=False)
    pst = pf.build_pst('freyberg.pst', version=2)
    # pst.write(os.path.join(pf.new_d, "freyberg.usg.pst"), version=2)
    pyemu.os_utils.run("{0} {1}".format(ies_exe_path, pst.filename.name),
                       cwd=pf.new_d)


def _add_big_obsffile(pf, profile=False, nchar=50000):
    if isinstance(pf, str):
        pstfrom_add = False
        wd = pf
    else:
        pstfrom_add = True
        wd = pf.new_d
    df = pd.DataFrame(np.random.random([10, nchar]),
                      columns=[hex(c) for c in range(nchar)])
    df.index.name = 'time'
    df.to_csv(os.path.join(wd, 'bigobseg.csv'))

    if pstfrom_add:
        if profile:
            import cProfile
            pr = cProfile.Profile()
            pr.enable()
            pf.add_observations('bigobseg.csv', index_cols='time')
            pr.disable()
            pr.print_stats(sort="cumtime")
        else:
            pf.add_observations('bigobseg.csv', index_cols='time')


def mf6_subdir_test():
    import numpy as np
    import pandas as pd
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    org_model_ws = os.path.join('..', 'examples', 'freyberg_mf6')
    tmp_model_ws = "temp_pst_from"
    sd = "sub_dir"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    tmp2_ws = os.path.join(tmp_model_ws, sd)
    sim = flopy.mf6.MFSimulation.load(sim_ws=org_model_ws)
    # sim.set_all_data_external()
    sim.set_sim_path(tmp2_ws)
    # sim.set_all_data_external()
    m = sim.get_model("freyberg6")
    sim.set_all_data_external(check_data=False)
    sim.write_simulation()

    # SETUP pest stuff...
    if bin_path == '':
        exe = mf6_exe_path  # bit of flexibility for local/server run
    else:
        exe = os.path.join('..', mf6_exe_path)
    os_utils.run("{0} ".format(exe), cwd=tmp2_ws)
    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # sr0 = m.sr
    # sr = pyemu.helpers.SpatialReference.from_namfile(
    #     os.path.join(tmp_model_ws, "freyberg6.nam"),
    #     delr=m.dis.delr.array, delc=m.dis.delc.array)
    sr = m.modelgrid
    # set up PstFrom object
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=True, spatial_reference=sr,
                 zero_based=False,start_datetime="1-1-2018",
                 chunk_len=1)
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')

    # call generic once so that the output file exists
    df = generic_function(os.path.join(template_ws, sd))

    # add the values in generic to the ctl file
    pf.add_observations(
        os.path.join(sd, "generic.csv"),
        insfile="generic.csv.ins",
        index_cols=["datetime", "index_2"],
        use_cols=["simval1", "simval2"]
    )
    # add the function call to make generic to the forward run script
    pf.add_py_function("pst_from_tests.py",f"generic_function('{sd}')",is_pre_cmd=False)

    # add a function that isnt going to be called directly
    pf.add_py_function("pst_from_tests.py","another_generic_function(some_arg)",is_pre_cmd=None)

    # pf.post_py_cmds.append("generic_function()")
    df = pd.read_csv(os.path.join(template_ws, sd, "sfr.csv"), index_col=0)
    pf.add_observations(os.path.join(sd, "sfr.csv"), index_cols="time", use_cols=list(df.columns.values))
    pf.add_observations(os.path.join(sd, "freyberg6.npf_k_layer1.txt"),
                        zone_array=m.dis.idomain.array[0])


    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    rch_temporal_gs = pyemu.geostats.GeoStruct(variograms=pyemu.geostats.ExpVario(contribution=1.0,a=60))
    pf.extra_py_imports.append('flopy')
    ib = m.dis.idomain[0].array
    tags = {"npf_k_":[0.1,10.],"npf_k33_":[.1,10],"sto_ss":[.1,10],"sto_sy":[.9,1.1],"rch_recharge":[.5,1.5]}
    dts = pd.to_datetime("1-1-2018") + pd.to_timedelta(np.cumsum(sim.tdis.perioddata.array["perlen"]),unit="d")
    print(dts)
    for tag,bnd in tags.items():
        lb,ub = bnd[0],bnd[1]
        arr_files = [os.path.join(sd, f) for f in os.listdir(os.path.join(tmp_model_ws, sd)) if tag in f and f.endswith(".txt")]
        if "rch" in tag:
            pf.add_parameters(filenames=arr_files, par_type="grid", par_name_base="rch_gr",
                              pargp="rch_gr", zone_array=ib, upper_bound=ub, lower_bound=lb,
                              geostruct=gr_gs)
            for arr_file in arr_files:
                kper = int(arr_file.split('.')[1].split('_')[-1]) - 1
                pf.add_parameters(filenames=arr_file,par_type="constant",par_name_base=arr_file.split('.')[1]+"_cn",
                                  pargp="rch_const",zone_array=ib,upper_bound=ub,lower_bound=lb,geostruct=rch_temporal_gs,
                                  datetime=dts[kper])
        else:
            for arr_file in arr_files:

                # these ult bounds are used later in an assert
                # and also are used so that the initial input array files
                # are preserved
                ult_lb = None
                ult_ub = None
                if "npf_k_" in arr_file:
                   ult_ub = 31.0
                   ult_lb = -1.3
                pf.add_parameters(filenames=arr_file,par_type="grid",par_name_base=arr_file.split('.')[1]+"_gr",
                                  pargp=arr_file.split('.')[1]+"_gr",zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  geostruct=gr_gs,ult_ubound=None if ult_ub is None else ult_ub + 1,
                                  ult_lbound=None if ult_lb is None else ult_lb + 1)
                # use a slightly lower ult bound here
                pf.add_parameters(filenames=arr_file, par_type="pilotpoints", par_name_base=arr_file.split('.')[1]+"_pp",
                                  pargp=arr_file.split('.')[1]+"_pp", zone_array=ib,upper_bound=ub,lower_bound=lb,
                                  ult_ubound=None if ult_ub is None else ult_ub - 1,
                                  ult_lbound=None if ult_lb is None else ult_lb - 1)
    #
    #
    # add SP1 spatially constant, but temporally correlated wel flux pars
    kper = 0
    list_file = os.path.join(
        sd, "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    )
    pf.add_parameters(filenames=list_file, par_type="constant",
                      par_name_base="twel_mlt_{0}".format(kper),
                      pargp="twel_mlt".format(kper), index_cols=[0, 1, 2],
                      use_cols=[3], upper_bound=1.5, lower_bound=0.5,
                      datetime=dts[kper], geostruct=rch_temporal_gs,
                      mfile_skip=1)
    #
    # # add temporally indep, but spatially correlated wel flux pars
    # pf.add_parameters(filenames=list_file, par_type="grid",
    #                   par_name_base="wel_grid_{0}".format(kper),
    #                   pargp="wel_{0}".format(kper), index_cols=[0, 1, 2],
    #                   use_cols=[3], upper_bound=1.5, lower_bound=0.5,
    #                   geostruct=gr_gs, mfile_skip=1)
    # kper = 1
    # list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    # pf.add_parameters(filenames=list_file, par_type="constant",
    #                   par_name_base="twel_mlt_{0}".format(kper),
    #                   pargp="twel_mlt".format(kper), index_cols=[0, 1, 2],
    #                   use_cols=[3], upper_bound=1.5, lower_bound=0.5,
    #                   datetime=dts[kper], geostruct=rch_temporal_gs,
    #                   mfile_skip='#')
    # # add temporally indep, but spatially correlated wel flux pars
    # pf.add_parameters(filenames=list_file, par_type="grid",
    #                   par_name_base="wel_grid_{0}".format(kper),
    #                   pargp="wel_{0}".format(kper), index_cols=[0, 1, 2],
    #                   use_cols=[3], upper_bound=1.5, lower_bound=0.5,
    #                   geostruct=gr_gs, mfile_skip='#')
    # kper = 2
    # list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    # pf.add_parameters(filenames=list_file, par_type="constant",
    #                   par_name_base="twel_mlt_{0}".format(kper),
    #                   pargp="twel_mlt".format(kper), index_cols=['#k', 'i', 'j'],
    #                   use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
    #                   datetime=dts[kper], geostruct=rch_temporal_gs)
    # # add temporally indep, but spatially correlated wel flux pars
    # pf.add_parameters(filenames=list_file, par_type="grid",
    #                   par_name_base="wel_grid_{0}".format(kper),
    #                   pargp="wel_{0}".format(kper), index_cols=['#k', 'i', 'j'],
    #                   use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
    #                   geostruct=gr_gs)
    # kper = 3
    # list_file = "freyberg6.wel_stress_period_data_{0}.txt".format(kper+1)
    # pf.add_parameters(filenames=list_file, par_type="constant",
    #                   par_name_base="twel_mlt_{0}".format(kper),
    #                   pargp="twel_mlt".format(kper), index_cols=['#k', 'i', 'j'],
    #                   use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
    #                   datetime=dts[kper], geostruct=rch_temporal_gs,
    #                   mfile_skip=1)
    # # add temporally indep, but spatially correlated wel flux pars
    # pf.add_parameters(filenames=list_file, par_type="grid",
    #                   par_name_base="wel_grid_{0}".format(kper),
    #                   pargp="wel_{0}".format(kper), index_cols=['#k', 'i', 'j'],
    #                   use_cols=['flux'], upper_bound=1.5, lower_bound=0.5,
    #                   geostruct=gr_gs, mfile_skip=1)
    # list_files = ["freyberg6.wel_stress_period_data_{0}.txt".format(t)
    #               for t in range(5, m.nper+1)]
    # for list_file in list_files:
    #     kper = int(list_file.split(".")[1].split('_')[-1]) - 1
    #     # add spatially constant, but temporally correlated wel flux pars
    #     pf.add_parameters(filenames=list_file,par_type="constant",par_name_base="twel_mlt_{0}".format(kper),
    #                       pargp="twel_mlt".format(kper),index_cols=[0,1,2],use_cols=[3],
    #                       upper_bound=1.5,lower_bound=0.5, datetime=dts[kper], geostruct=rch_temporal_gs)
    #
    #     # add temporally indep, but spatially correlated wel flux pars
    #     pf.add_parameters(filenames=list_file, par_type="grid", par_name_base="wel_grid_{0}".format(kper),
    #                       pargp="wel_{0}".format(kper), index_cols=[0, 1, 2], use_cols=[3],
    #                       upper_bound=1.5, lower_bound=0.5, geostruct=gr_gs)
    #
    # # test non spatial idx in list like
    # pf.add_parameters(filenames="freyberg6.sfr_packagedata_test.txt", par_name_base="sfr_rhk",
    #                   pargp="sfr_rhk", index_cols=['#rno'], use_cols=['rhk'], upper_bound=10.,
    #                   lower_bound=0.1,
    #                   par_type="grid")
    #
    # # add model run command
    pf.pre_py_cmds.append(f"os.chdir('{sd}')")
    pf.mod_sys_cmds.append("mf6")
    pf.post_py_cmds.insert(0, "os.chdir('..')")
    print(pf.mult_files)
    print(pf.org_files)

    # build pest
    pst = pf.build_pst('freyberg.pst')

    # # quick check of write and apply method
    # pars = pst.parameter_data
    # # set reach 1 hk to 100
    # sfr_pars = pars.loc[pars.parnme.str.startswith('sfr')].index
    # pars.loc[sfr_pars, 'parval1'] = np.random.random(len(sfr_pars)) * 10
    #
    # sfr_pars = pars.loc[sfr_pars].copy()
    # sfr_pars[['inst', 'usecol', '#rno']] = sfr_pars.parnme.apply(
    #     lambda x: pd.DataFrame([s.split(':') for s in x.split('_')
    #                             if ':' in s]).set_index(0)[1])
    #
    # sfr_pars['#rno'] = sfr_pars['#rno'] .astype(int)
    # os.chdir(pf.new_d)
    # pst.write_input_files()
    # try:
    #     pyemu.helpers.apply_list_and_array_pars()
    # except Exception as e:
    #     os.chdir('..')
    #     raise e
    # os.chdir('..')
    # # verify apply
    # df = pd.read_csv(os.path.join(
    #     pf.new_d, "freyberg6.sfr_packagedata_test.txt"),
    #     delim_whitespace=True, index_col=0)
    # df.index = df.index - 1
    # print(df.rhk)
    # print((sfr_pkgdf.set_index('rno').loc[df.index, 'rhk'] *
    #              sfr_pars.set_index('#rno').loc[df.index, 'parval1']))
    # assert np.isclose(
    #     df.rhk, (sfr_pkgdf.set_index('rno').loc[df.index, 'rhk'] *
    #              sfr_pars.set_index('#rno').loc[df.index, 'parval1'])).all()
    # pars.loc[sfr_pars.index, 'parval1'] = 1.0
    #
    # # add more:
    # pf.add_parameters(filenames="freyberg6.sfr_packagedata.txt", par_name_base="sfr_rhk",
    #                   pargp="sfr_rhk", index_cols={'k': 1, 'i': 2, 'j': 3}, use_cols=[9], upper_bound=10.,
    #                   lower_bound=0.1,
    #                   par_type="grid", rebuild_pst=True)
    #
    # df = pd.read_csv(os.path.join(tmp_model_ws, "heads.csv"), index_col=0)
    pf.add_observations(os.path.join(sd, "heads.csv"),
                        insfile=os.path.join(sd, "heads.csv.ins"),
                        index_cols="time",
                        prefix="hds",
                        rebuild_pst=True)
    #
    # # test par mults are working
    b_d = os.getcwd()
    os.chdir(pf.new_d)
    try:
        pyemu.helpers.apply_list_and_array_pars(
            arr_par_file="mult2model_info.csv",chunk_len=1)
    except Exception as e:
        os.chdir(b_d)
        raise Exception(str(e))
    os.chdir(b_d)
    #
    # cov = pf.build_prior(fmt="none").to_dataframe()
    # twel_pars = [p for p in pst.par_names if "twel_mlt" in p]
    # twcov = cov.loc[twel_pars,twel_pars]
    # dsum = np.diag(twcov.values).sum()
    # assert twcov.sum().sum() > dsum
    #
    # rch_cn = [p for p in pst.par_names if "_cn" in p]
    # print(rch_cn)
    # rcov = cov.loc[rch_cn,rch_cn]
    # dsum = np.diag(rcov.values).sum()
    # assert rcov.sum().sum() > dsum
    #
    # num_reals = 100
    # pe = pf.draw(num_reals, use_specsim=True)
    # pe.to_binary(os.path.join(template_ws, "prior.jcb"))
    # assert pe.shape[1] == pst.npar_adj, "{0} vs {1}".format(pe.shape[0], pst.npar_adj)
    # assert pe.shape[0] == num_reals
    #
    #
    pst.control_data.noptmax = 0
    pst.pestpp_options["additional_ins_delimiters"] = ","
    #
    pst.write(os.path.join(pf.new_d, "freyberg.pst"))
    pyemu.os_utils.run("{0} freyberg.pst".format(ies_exe_path), cwd=pf.new_d)
    #
    res_file = os.path.join(pf.new_d, "freyberg.base.rei")
    assert os.path.exists(res_file), res_file
    pst.set_res(res_file)
    print(pst.phi)
    #assert pst.phi < 1.0e-5, pst.phi
    #
    # check mult files are in pst input files
    csv = os.path.join(template_ws, "mult2model_info.csv")
    df = pd.read_csv(csv, index_col=0)
    pst_input_files = {str(f) for f in pst.input_files}
    mults_not_linked_to_pst = ((set(df.mlt_file.unique()) -
                                pst_input_files) -
                               set(df.loc[df.pp_file.notna()].mlt_file))
    assert len(mults_not_linked_to_pst) == 0, print(mults_not_linked_to_pst)

    # make sure the appropriate ult bounds have made it thru
    # df = pd.read_csv(os.path.join(template_ws,"mult2model_info.csv"))
    # print(df.columns)
    # df = df.loc[df.model_file.apply(lambda x: "npf_k_" in x),:]
    # print(df)
    # print(df.upper_bound)
    # print(df.lower_bound)
    # assert np.abs(float(df.upper_bound.min()) - 30.) < 1.0e-6,df.upper_bound.min()
    # assert np.abs(float(df.lower_bound.max()) - -0.3) < 1.0e-6,df.lower_bound.max()


def shortname_conversion_test():
    import numpy as np
    import pandas as pd
    import re
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    try:
        import flopy
    except:
        return

    tmp_model_ws = "temp_pst_from"
    if os.path.exists(tmp_model_ws):
        shutil.rmtree(tmp_model_ws)
    os.mkdir(tmp_model_ws)
    dims = (20,60)
    np.savetxt(os.path.join(tmp_model_ws,"parfile1"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "parfile2"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "parfile3"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "parfile4"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "parfile5"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "parfile6"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "obsfile1"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "obsfile2"), np.ones(dims))

    np.savetxt(os.path.join(tmp_model_ws, "parfile7"), np.ones(dims))
    np.savetxt(os.path.join(tmp_model_ws, "obsfile3"), np.ones(dims))
    # SETUP pest stuff...

    template_ws = "new_temp"
    if os.path.exists(template_ws):
        shutil.rmtree(template_ws)
    # set up PstFrom object
    # obs
    #   using tabular style model output
    #   (generated by pyemu.gw_utils.setup_hds_obs())
    # pf.add_observations('freyberg.hds.dat', insfile='freyberg.hds.dat.ins2',
    #                     index_cols='obsnme', use_cols='obsval', prefix='hds')
    sr = pyemu.helpers.SpatialReference(delr=[10]*dims[1],
                                        delc=[10]*dims[0],
                                        rotation=0,
                                        epsg=3070,
                                        xul=0.,
                                        yul=0.,
                                        units='meters',  # gis units of meters?
                                        lenuni=2  # model units of meters
                                        )
    pf = PstFrom(original_d=tmp_model_ws, new_d=template_ws,
                 remove_existing=True,
                 longnames=False,
                 zero_based=False,
                 spatial_reference=sr)

    v = pyemu.geostats.ExpVario(contribution=1.0, a=1000)
    gr_gs = pyemu.geostats.GeoStruct(variograms=v)
    c = 0
    parfiles = [f.name for f in Path(template_ws).glob("parfile*")][0:3]
    for f in parfiles:
        c += 1
        pf.add_parameters(filenames=f, par_type="grid",
                          par_name_base=f"par{c}",
                          pargp=f"pargp{c}", upper_bound=0.1, lower_bound=10.0,
                          geostruct=gr_gs)
    pf.add_parameters(filenames=parfiles,
                      par_type="constant", par_name_base="cpar",
                      pargp="cpargp", upper_bound=0.1, lower_bound=10.0,
                      geostruct=gr_gs)
    pf.add_observations(
        "obsfile1",
        prefix="longobservationname",
        rebuild_pst=False,
        obsgp="longobservationgroup",
        includes_header=False
    )
    pf.add_observations(
        "obsfile2",
        prefix="longobservationname2",
        rebuild_pst=False,
        obsgp="longobservationgroup2",
        includes_header=False
    )
    pf.add_observations(
        "obsfile3",
        prefix="longobservationname-lt",
        rebuild_pst=False,
        obsgp="less_longobservationgroup",
        includes_header=False,
        insfile="lt_obsfile3.ins"
    )
    pf.add_observations(
        "obsfile3",
        prefix="longobservationname-gt",
        rebuild_pst=False,
        obsgp="greater_longobservationgroup",
        includes_header=False,
        insfile="gt_obsfile3.ins"
    )
    pst = pf.build_pst()
    obs = set(pst.observation_data.obsnme)
    trie = pyemu.helpers.Trie()
    [trie.add(ob) for ob in obs]
    rex = re.compile(trie.pattern())
    for ins in pst.instruction_files:
        with open(os.path.join(pf.new_d, ins), "rt") as f:
            obsin = set(rex.findall(f.read()))
        obs = obs - obsin
    assert len(obs) == 0, f"{len(obs)} obs not found in insfiles: {obs[:100]}..."

    par = set(pst.parameter_data.parnme)
    trie = pyemu.helpers.Trie()
    [trie.add(p) for p in par]
    rex = re.compile(trie.pattern())
    for tpl in pst.template_files:
        with open(os.path.join(pf.new_d, tpl), "rt") as f:
            parin = set(rex.findall(f.read()))
        par = par - parin
    assert len(par) == 0, f"{len(par)} pars not found in tplfiles: {par[:100]}..."
    # test update/rebuild
    pf.add_observations(
        "obsfile3",
        prefix="longobservationname3",
        rebuild_pst=True,
        obsgp="longobservationgroup3",
        includes_header=False
    )
    pf.add_parameters(filenames="parfile7",
                      par_type="grid", par_name_base="par7",
                      pargp="par7", upper_bound=0.1, lower_bound=10.0,
                      geostruct=gr_gs,
                      rebuild_pst=True)

    obs = set(pst.observation_data.obsnme)
    trie = pyemu.helpers.Trie()
    [trie.add(ob) for ob in obs]
    rex = re.compile(trie.pattern())
    for ins in pst.instruction_files:
        with open(os.path.join(pf.new_d, ins), "rt") as f:
            obsin = set(rex.findall(f.read()))
        obs = obs - obsin
    assert len(obs) == 0, f"{len(obs)} obs not found in insfiles: {obs[:100]}..."

    par = set(pst.parameter_data.parnme)
    parin = set()
    trie = pyemu.helpers.Trie()
    [trie.add(p) for p in par]
    rex = re.compile(trie.pattern())
    for tpl in pst.template_files:
        with open(os.path.join(pf.new_d, tpl), "rt") as f:
            parin = set(rex.findall(f.read()))
        par = par - parin
    assert len(par) == 0, f"{len(par)} pars not found in tplfiles: {par[:100]}..."


if __name__ == "__main__":
    # mf6_freyberg_pp_locs_test()
    # invest()
    # freyberg_test()
    # freyberg_prior_build_test()
    # mf6_freyberg_test()
    #$mf6_freyberg_da_test()
    #shortname_conversion_test()
    #mf6_freyberg_shortnames_test()
    mf6_freyberg_direct_test()
    #mf6_freyberg_varying_idomain()
    # xsec_test()
    # mf6_freyberg_short_direct_test()
    # mf6_add_various_obs_test()
    # mf6_subdir_test()
    #tpf = TestPstFrom()
    #tpf.setup()
    #tpf.test_add_array_parameters_to_file_list()
    #tpf.test_add_array_parameters_alt_inst_str_none_m()
    #tpf.test_add_array_parameters_alt_inst_str_0_d()
    # tpf.test_add_array_parameters_pps_grid()
    #tpf.test_add_list_parameters()
    # # pstfrom_profile()
    # mf6_freyberg_arr_obs_and_headerless_test()
    #usg_freyberg_test()



