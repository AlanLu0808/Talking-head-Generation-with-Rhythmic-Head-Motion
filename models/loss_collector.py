# Copyright (c) 2019, NVIDIA Corporation. All rights reserved.
#
# This work is made available
# under the Nvidia Source Code License (1-way Commercial).
# To view a copy of this license, visit
# https://nvlabs.github.io/few-shot-vid2vid/License.txt
import torch
from util.image_pool import ImagePool
from util.util import get_roi
from models.base_model import BaseModel
import models.networks as networks
from models.input_process import *
from pytorch_msssim import msssim

import pdb

class LossCollector(BaseModel):
    def name(self):
        return 'LossCollector'

    def initialize(self, opt):
        BaseModel.initialize(self, opt)        
        
        # define losses
        self.define_losses() 
        self.tD = 1           

    ####################################### loss related ################################################
    def define_losses(self):
        opt = self.opt
        # set loss functions
        if self.isTrain or opt.finetune:
            self.fake_pool = ImagePool(0)
            self.old_lr = opt.lr
                
            # define loss functions
            self.criterionGAN = networks.GANLoss(opt.gan_mode, tensor=self.Tensor, opt=opt)
            self.criterionFeat = torch.nn.L1Loss()
            self.criterionFlow = networks.MaskedL1Loss()
            self.criterionGen = torch.nn.L1Loss()
            if not opt.no_vgg_loss:
                self.criterionVGG = networks.VGGLoss(opt, self.gpu_ids)
        
            # Names so we can breakout loss
            self.loss_names_G = ['G_GAN', 'G_GAN_Feat', \
                                 'G_VGG', 'GM_VGG', \
                                 'GT_GAN', 'GT_GAN_Feat', \
                                 'GM_GAN', 'GM_GAN_Feat', \
                                 'ssmi', 'ssmi_M', \
                                 'F_Flow', 'F_Warp', 'L1_Loss', 'Atten_L1_Loss', 'W']
            self.loss_names_D = ['D_real', 'D_fake', 'DM_real', 'DM_fake', 'DT_real', 'DT_fake'] 
            self.loss_names = self.loss_names_G + self.loss_names_D

    def discriminate(self, netD, tgt_label, fake_image, tgt_image, ref_image, for_discriminator):
        tgt_concat = torch.cat([fake_image, tgt_image], dim=0)
        if tgt_label is not None:
            tgt_concat = torch.cat([tgt_label.repeat(2, 1, 1, 1), tgt_concat], dim=1)
            
        if ref_image is not None:             
            ref_image = ref_image.repeat(2, 1, 1, 1)
            if self.concat_ref_for_D:
                tgt_concat = torch.cat([ref_image, tgt_concat], dim=1)
                ref_image = None        

        discriminator_out = netD(tgt_concat, ref_image)
        pred_fake, pred_real = self.divide_pred(discriminator_out)

        if for_discriminator:
            loss_D_real = self.criterionGAN(pred_real, True)
            loss_D_fake = self.criterionGAN(pred_fake, False)            
            return [loss_D_real, loss_D_fake]
        else:
            loss_G_GAN = self.criterionGAN(pred_fake, True)
            loss_G_GAN_Feat = self.GAN_matching_loss(pred_real, pred_fake, for_discriminator)            
            return [loss_G_GAN, loss_G_GAN_Feat]

    def compute_GAN_losses(self, nets, data_list, for_discriminator, for_temporal=False):        
        if for_temporal and self.tD < 2:
            return [self.Tensor(1).fill_(0), self.Tensor(1).fill_(0)]
        tgt_label, tgt_image, fake_image, ref_label, ref_image = data_list
        netD, netDT = nets
        if isinstance(fake_image, list):
            fake_image = [x for x in fake_image if x is not None]
            losses = [self.compute_GAN_losses(nets, [tgt_label, real_i, fake_i, ref_label, ref_image], 
                for_discriminator, for_temporal) for fake_i, real_i in zip(fake_image, tgt_image)]
            return [sum([item[i] for item in losses]) for i in range(len(losses[0]))]
                        
        tgt_label, tgt_image, fake_image = self.reshape([tgt_label, tgt_image, fake_image], for_temporal)
        
        # main discriminator loss        
        input_label = ref_concat = None
        if not for_temporal:            
            t = self.opt.n_frames_per_gpu
            ref_label, ref_image = ref_label.repeat(t,1,1,1), ref_image.repeat(t,1,1,1)                  
            input_label = tgt_label
            ref_concat = torch.cat([ref_label, ref_image], dim=1)

        netD = netD if not for_temporal else netDT        
        losses = self.discriminate(netD, input_label, fake_image, tgt_image, ref_concat, for_discriminator=for_discriminator)
        if for_temporal: 
            if not for_discriminator: losses = [loss * self.opt.lambda_temp for loss in losses]
            return losses
   
        return losses

    def compute_mouth_losses(self, nets, data_list, for_discriminator):
        tgt_image, fake_image = data_list
        netDm = nets
        if isinstance(fake_image, list):
            fake_image = [x for x in fake_image if x is not None]
            losses = [self.compute_mouth_losses(nets, [real_i, fake_i], for_discriminator) \
                for fake_i, real_i in zip(fake_image, tgt_image)]
            return [sum([item[i] for item in losses]) for i in range(len(losses[0]))]

        tgt_image, fake_image = self.reshape([tgt_image, fake_image])

        # discriminator loss
        losses = self.discriminate(netDm, None, fake_image, tgt_image, None, for_discriminator)

        return losses

    def compute_new_GAN_losses(self, netD, data_list, is_real):
        tgt_img, ref_img, lmark = self.reshape(data_list[:-1], for_temporal=False)
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])
        preds, losses = netD(tgt_img, ref_img, lmark, audio, is_real)
        return preds, losses

    def compute_mismatch_GAN_losses(self, netD, data_list):
        tgt_ref_mis_img, tgt_lmark_mis_img, tgt_audio_mis_img, ref_img, lmark = self.reshape(data_list[:-1], for_temporal=False)
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])
        ref_mis_preds, ref_mis_losses = netD(tgt_ref_mis_img, ref_img, None, None, is_real=False)
        lmark_mis_preds, lmark_mis_losses = netD(tgt_lmark_mis_img, None, lmark, None, is_real=False)
        audio_mis_preds, audio_mis_losses = netD(tgt_audio_mis_img, None, None, audio, is_real=False)

        preds = [ref_mis_preds[0], lmark_mis_preds[1], audio_mis_preds[2]]
        losses = [ref_mis_losses[0], lmark_mis_losses[1], audio_mis_losses[2]]

        return preds, losses

    def compute_mismatch_GAN_losses_addition(self, netD, data_list, for_discriminator, is_real, tgt_img=None):
        tgt_ref_mis_img, tgt_lmark_mis_img, tgt_audio_mis_img, ref_img, lmark = self.reshape(data_list[:-1], for_temporal=False)
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])
        ref_mis_res = netD(tgt_ref_mis_img, ref_img, None, None)
        lmark_mis_res = netD(tgt_lmark_mis_img, None, lmark, None)
        audio_mis_res = netD(tgt_audio_mis_img, None, None, audio)

        ref_loss = self.criterionGAN(ref_mis_res[0], is_real)
        lmark_loss = self.criterionGAN(lmark_mis_res[1], is_real)
        audio_loss = self.criterionGAN(audio_mis_res[2], is_real)
        loss = [ref_loss + lmark_loss + audio_loss]
        if not for_discriminator:
            assert tgt_img is not None
            tgt_img = self.reshape(tgt_img, for_temporal=False)
            tgt_ref_res, tgt_lmark_res, tgt_audio_res = netD(tgt_img, ref_img, lmark, audio)
            fea_losses = [self.GAN_matching_loss(ref_mis_res[0], tgt_ref_res, for_discriminator), \
                          self.GAN_matching_loss(lmark_mis_res[1], tgt_lmark_res, for_discriminator),\
                          self.GAN_matching_loss(audio_mis_res[2], tgt_audio_res, for_discriminator)]
            loss.append(sum(fea_losses))

        return loss

    def compute_GAN_losses_addition(self, netD, data_list, for_discriminator, is_real, tgt_img=None):
        img, ref_img, lmark = self.reshape(data_list[:-1], for_temporal=False)
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])
        ref_res, lmark_res, audio_res = netD(img, ref_img, lmark, audio)

        ref_loss = self.criterionGAN(ref_res, is_real)
        lmark_loss = self.criterionGAN(lmark_res, is_real)
        audio_loss = self.criterionGAN(audio_res, is_real)
        loss = [ref_loss + lmark_loss + audio_loss]
        if not for_discriminator:
            assert tgt_img is not None
            tgt_img = self.reshape(tgt_img, for_temporal=False)
            tgt_ref_res, tgt_lmark_res, tgt_audio_res = netD(tgt_img, ref_img, lmark, audio)
            fea_losses = [self.GAN_matching_loss(ref_res, tgt_ref_res, for_discriminator), \
                          self.GAN_matching_loss(lmark_res, tgt_lmark_res, for_discriminator),\
                          self.GAN_matching_loss(audio_res, tgt_audio_res, for_discriminator)]
            loss.append(sum(fea_losses))

        return loss

    def compute_mouth_losses_addition(self, netD, data_list, for_discriminator, is_real, tgt_img=None):
        img = self.reshape(data_list[:-1], for_temporal=False)[0]
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])

        audio_res = netD(img, audio)
        loss = [self.criterionGAN(audio_res, is_real)]
        if not for_discriminator:
            assert tgt_img is not None
            tgt_img = self.reshape(tgt_img, for_temporal=False)
            tgt_audio_res = netD(tgt_img, audio)
            fea_loss = self.GAN_matching_loss(audio_res, tgt_audio_res, for_discriminator)
            loss.append(fea_loss)

        return loss

    def compute_new_mouth_losses(self, netDm, data_list, is_real):
        tgt_img = self.reshape(data_list[:-1], for_temporal=False)[0]
        audio = data_list[-1].reshape(-1, 1, data_list[-1].shape[-1])
        preds, losses = netDm(tgt_img, audio, is_real)
        return preds, losses

    def compute_VGG_losses(self, fake_image, fake_raw_image, img_ani, tgt_image):
        loss_G_VGG = self.Tensor(1).fill_(0)
        opt = self.opt
        if not opt.no_vgg_loss:
            if fake_image is not None:
                loss_G_VGG = self.criterionVGG(fake_image, tgt_image) * opt.lambda_vgg
            if fake_raw_image is not None:
                loss_G_VGG += self.criterionVGG(fake_raw_image, tgt_image) * opt.lambda_vgg
            if img_ani is not None:
                loss_G_VGG += self.criterionVGG(img_ani, tgt_image) * opt.lambda_vgg
        return loss_G_VGG

    def compute_flow_losses(self, flow, warped_image, tgt_image, tgt_crop_image, flow_gt, conf_gt):                    
        loss_F_Flow_r, loss_F_Warp_r = self.compute_flow_loss(flow[0], warped_image[0], tgt_image, flow_gt[0], conf_gt[0])
        loss_F_Flow_p, loss_F_Warp_p = self.compute_flow_loss(flow[1], warped_image[1], tgt_image, flow_gt[1], conf_gt[1])
        loss_F_Flow_a, loss_F_Warp_a = self.compute_flow_loss(flow[2], warped_image[2], tgt_crop_image, flow_gt[2], conf_gt[2])
        loss_F_Flow = loss_F_Flow_p + loss_F_Flow_r + loss_F_Flow_a
        loss_F_Warp = loss_F_Warp_p + loss_F_Warp_r + loss_F_Warp_a
        
        return loss_F_Flow, loss_F_Warp

    def compute_flow_loss(self, flow, warped_image, tgt_image, flow_gt, conf_gt):
        lambda_flow = self.opt.lambda_flow
        loss_F_Flow, loss_F_Warp = self.Tensor(1).fill_(0), self.Tensor(1).fill_(0)
        if self.opt.isTrain and flow is not None:
            if flow_gt is not None:               
                loss_F_Flow = self.criterionFlow(flow, flow_gt, conf_gt) * lambda_flow
            loss_F_Warp = self.criterionFeat(warped_image, tgt_image) * lambda_flow
        return loss_F_Flow, loss_F_Warp

    def compute_weight_losses(self, weight, warped_image, tgt_image, tgt_crop_image):         
        loss_W = self.Tensor(1).fill_(0)
        if self.opt.use_weight_loss:
            loss_W += self.compute_weight_loss(weight[0], warped_image[0], tgt_image)        
            loss_W += self.compute_weight_loss(weight[1], warped_image[1], tgt_image)
            loss_W += self.compute_weight_loss(weight[2], warped_image[2], tgt_crop_image)
        
        return loss_W

    def compute_weight_loss(self, weight, warped_image, tgt_image):
        loss_W = 0
        if self.opt.isTrain and weight is not None:
            img_diff = torch.sum(abs(warped_image - tgt_image), dim=1, keepdim=True)
            conf = torch.clamp(1 - img_diff, 0, 1)

            dummy0, dummy1 = torch.zeros_like(weight), torch.ones_like(weight)        
            loss_W = self.criterionFlow(weight, dummy0, conf) * self.opt.lambda_weight
            loss_W += self.criterionFlow(weight, dummy1, 1-conf) * self.opt.lambda_weight
        return loss_W

    def GAN_matching_loss(self, pred_real, pred_fake, for_discriminator=False):
        loss_G_GAN_Feat = self.Tensor(1).fill_(0)
        if not for_discriminator and not self.opt.no_ganFeat_loss:            
            feat_weights = 1
            num_D = len(pred_fake)
            D_weights = 1.0 / num_D            
            for i in range(num_D):
                for j in range(len(pred_fake[i])-1):
                    unweighted_loss = self.criterionFeat(pred_fake[i][j], pred_real[i][j].detach())
                    loss_G_GAN_Feat += D_weights * feat_weights * unweighted_loss * self.opt.lambda_feat            
        return loss_G_GAN_Feat


    def compute_L1_loss(self, syn_image, tgt_image):
        loss_l1 = self.criterionGen(syn_image, tgt_image) * self.opt.face_l1
        return loss_l1

    def atten_L1_loss(self, syn_image, tgt_image, tgt_template):
        loss_atten = self.criterionGen(syn_image * tgt_template, tgt_image * tgt_template) * self.opt.mask_l1
        return loss_atten

    def compute_msssim_loss(self, tgt_image, syn_image):
        tgt_image, syn_image = self.reshape([tgt_image, syn_image], for_temporal=False)
        loss = 1 - msssim(tgt_image, syn_image)
        return loss


def loss_backward(opt, losses, optimizer):    
    losses = [ torch.mean(x) if not isinstance(x, int) else x for x in losses ]
    loss = sum(losses)        
    optimizer.zero_grad()                
    if opt.fp16:
        from apex import amp
        with amp.scale_loss(loss, optimizer) as scaled_loss: 
            scaled_loss.backward()
    else:
        loss.backward()
    optimizer.step()
    return losses