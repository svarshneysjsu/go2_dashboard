"""
  Generated by Eclipse Cyclone DDS idlc Python Backend
  Cyclone DDS IDL version: v0.11.0
  Module: unitree_go.msg.dds_
  IDL file: HeightMap_.idl

"""

from enum import auto
from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

import cyclonedds.idl as idl
import cyclonedds.idl.annotations as annotate
import cyclonedds.idl.types as types

# root module import for resolving types
# import unitree_go


@dataclass
@annotate.final
@annotate.autoid("sequential")
class HeightMap_(idl.IdlStruct, typename="unitree_go.msg.dds_.HeightMap_"):
    stamp: types.float64
    frame_id: str
    resolution: types.float32
    width: types.uint32
    height: types.uint32
    origin: types.array[types.float32, 2]
    data: types.sequence[types.float32]


