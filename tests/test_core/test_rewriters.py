import argparse
import tempfile
from os import path as osp
from typing import Dict
from unittest.mock import MagicMock, patch

import mmcv
import pytest

from siatune.core.rewriters import (REWRITERS, AttachTrialInfoToPath,
                                    BaseRewriter, BatchConfigPatcher,
                                    CustomHookRegister, Dump, InstantiateCfg,
                                    MergeConfig, ResumeFromCkpt,
                                    SequeunceConfigPatcher, build_rewriter)
from siatune.utils import dump_cfg


def test_base_rewriter():
    with pytest.raises(TypeError):
        BaseRewriter()
    assert getattr(BaseRewriter, '__call__', None) is not None


def test_build_base_cfg():

    @REWRITERS.register_module()
    class DummyRewriter(BaseRewriter):

        def __call__(self, context: Dict) -> Dict:
            return context

    assert isinstance(
        build_rewriter(dict(type='DummyRewriter')), DummyRewriter)


@patch('ray.air.session.get_trial_id')
def test_dump(mock_get_trial_id):
    mock_get_trial_id.return_value = 'test'
    dump = Dump(key='cfg')
    config = mmcv.Config(dict())
    args = argparse.Namespace()
    args.config = config
    context = dict(cfg=config, args=args)
    dump(context)

    tmp_path = osp.join(tempfile.gettempdir(), 'test.py')
    # the dumped file name follows the return value of
    # `ray.tune.get_trial_id` as f'{trial_id}.py'.
    assert context['args'].config == tmp_path
    assert osp.exists(tmp_path)
    assert mmcv.utils.Config.fromfile(tmp_path)._cfg_dict == config._cfg_dict


def test_instantiate():
    dump_cfg(mmcv.utils.Config(dict(test='test')), 'test.py')

    instantiate = InstantiateCfg(key='cfg')
    args = argparse.Namespace()
    args.config = 'test.py'
    context = dict(args=args)
    instantiate(context)

    assert context['cfg']._cfg_dict == mmcv.utils.Config(
        dict(test='test'))._cfg_dict


def test_merge():
    merger = MergeConfig(src_key='src', dst_key='dst', key='cp')

    context = dict(
        src=mmcv.Config(dict(a=1, b=2)),
        dst=mmcv.Config(dict(c=3, d=4)),
    )

    merger(context)
    assert context['cp']._cfg_dict == mmcv.Config(dict(a=1, b=2, c=3,
                                                       d=4))._cfg_dict


def test_patch():
    from siatune.core.rewriters.patch import unwrap_regexp
    assert unwrap_regexp('$(a)') == ('a', True)

    context = dict(
        batch_test_cfg=mmcv.Config({'$(a & b)': 0}),
        seq_test_cfg=mmcv.Config({'$(c - d)': [1, 2]}))
    batch_config_patcher = BatchConfigPatcher(key='batch_test_cfg')
    seq_config_patcher = SequeunceConfigPatcher(key='seq_test_cfg')

    context = batch_config_patcher(context)
    assert context['batch_test_cfg']._cfg_dict == mmcv.Config({
        'a': 0,
        'b': 0
    })._cfg_dict
    context = seq_config_patcher(context)
    assert context['seq_test_cfg']._cfg_dict == mmcv.Config({
        'c': 1,
        'd': 2
    })._cfg_dict


@patch('ray.air.session.get_trial_id')
def test_append_trial_info_to_path(mock_get_trial_id):
    mock_get_trial_id.return_value = 'test'
    args = argparse.Namespace()
    args.work_dir = '/tmp'
    context = dict(args=args)
    suffix = AttachTrialInfoToPath()
    context = suffix(context)
    assert context['args'].work_dir == '/tmp/test'


def test_register():
    post_custom_hooks = ['a', 'b']
    register = CustomHookRegister(
        key='cfg', post_custom_hooks=post_custom_hooks)
    cfg = MagicMock()
    cfg.custom_hooks = []
    context = dict(cfg=cfg)

    context = register(context)
    assert context['cfg'].custom_hooks == post_custom_hooks


@patch('ray.air.session.get_checkpoint')
def test_resume_ckpt(mock_get_checkpoint):

    def to_dict():
        return dict(path='test.pth')

    ckpt = MagicMock()
    ckpt.to_dict = to_dict

    mock_get_checkpoint.return_value = ckpt

    args = argparse.Namespace()
    context = dict(args=args)

    resume_from_ckpt = ResumeFromCkpt()
    context = resume_from_ckpt(context)
    assert context.get('args').resume_from == 'test.pth'
