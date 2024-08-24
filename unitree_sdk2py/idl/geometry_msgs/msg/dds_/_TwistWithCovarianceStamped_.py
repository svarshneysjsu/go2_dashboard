"""
  Generated by Eclipse Cyclone DDS idlc Python Backend
  Cyclone DDS IDL version: v0.11.0
  Module: geometry_msgs.msg.dds_
  IDL file: TwistWithCovarianceStamped_.idl

"""

from enum import auto
from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

import cyclonedds.idl as idl
import cyclonedds.idl.annotations as annotate
import cyclonedds.idl.types as types

# root module import for resolving types
# import geometry_msgs

# if TYPE_CHECKING:
#     import std_msgs.msg.dds_



@dataclass
@annotate.final
@annotate.autoid("sequential")
class TwistWithCovarianceStamped_(idl.IdlStruct, typename="geometry_msgs.msg.dds_.TwistWithCovarianceStamped_"):
    header: 'unitree_sdk2py.idl.std_msgs.msg.dds_.Header_'
    twist: 'unitree_sdk2py.idl.geometry_msgs.msg.dds_.TwistWithCovariance_'


